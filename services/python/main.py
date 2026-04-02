import asyncio
import logging
import os
import urllib.parse

import aio_pika
from fastapi import FastAPI
from pydantic import BaseModel
from opentelemetry import metrics, propagate, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "app")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "app")
RABBITMQ_VHOST = os.getenv("RABBITMQ_VHOST", "/rapidmq")

EXCHANGE = "rapidmq.exchange"
ROUTING_KEY = "rapidmq.key"
QUEUE = "rapidmq.queue"

OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "rapidmq-python")

app = FastAPI()

connection = None
channel = None


def setup_otel() -> None:
    resource = Resource.create({"service.name": SERVICE_NAME})

    trace_provider = TracerProvider(resource=resource)
    span_exporter = OTLPSpanExporter(endpoint=OTEL_ENDPOINT, insecure=True)
    trace_provider.add_span_processor(BatchSpanProcessor(span_exporter))
    trace.set_tracer_provider(trace_provider)

    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=OTEL_ENDPOINT, insecure=True)
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    log_exporter = OTLPLogExporter(endpoint=OTEL_ENDPOINT, insecure=True)
    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
    set_logger_provider(logger_provider)

    handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)


@app.on_event("startup")
async def startup() -> None:
    setup_otel()
    await connect_rabbitmq()
    asyncio.create_task(consume_loop())


async def connect_rabbitmq() -> None:
    global connection, channel

    vhost = urllib.parse.quote(RABBITMQ_VHOST, safe="")
    url = f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASS}@{RABBITMQ_HOST}:{RABBITMQ_PORT}/{vhost}"

    connection = await aio_pika.connect_robust(url)
    channel = await connection.channel()

    exchange = await channel.declare_exchange(EXCHANGE, durable=True)
    queue = await channel.declare_queue(QUEUE, durable=True)
    await queue.bind(exchange, ROUTING_KEY)


async def consume_loop() -> None:
    queue = await channel.get_queue(QUEUE)

    async with queue.iterator() as queue_iter:
        async for message in queue_iter:
            async with message.process():
                ctx = propagate.extract(message.headers or {})
                tracer = trace.get_tracer("rapidmq-python")
                with tracer.start_as_current_span("rabbitmq.consume", context=ctx):
                    logging.info("Consumed message: %s", message.body.decode())


class PublishBody(BaseModel):
    message: str


@app.post("/publish")
async def publish(body: PublishBody) -> dict:
    tracer = trace.get_tracer("rapidmq-python")
    with tracer.start_as_current_span("rabbitmq.publish"):
        headers = {}
        propagate.inject(headers)

        exchange = await channel.get_exchange(EXCHANGE)
        message = aio_pika.Message(
            body=body.message.encode(),
            headers=headers,
        )
        await exchange.publish(message, routing_key=ROUTING_KEY)
        logging.info("Published message: %s", body.message)

    return {"status": "ok", "message": body.message}


def run() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8082)


if __name__ == "__main__":
    run()
