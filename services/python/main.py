import asyncio
import sys
import logging
import os
import urllib.parse

import aio_pika
from opentelemetry import trace, metrics, propagate
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk.resources import Resource, SERVICE_NAME as RESOURCE_SERVICE_NAME
from opentelemetry.trace import SpanKind

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "app")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "app")
RABBITMQ_VHOST = os.getenv("RABBITMQ_VHOST", "/rapidmq")

EXCHANGE = "rapidmq.exchange"
ROUTING_KEY = "rapidmq.key"
QUEUE = os.getenv("RABBITMQ_QUEUE", "rapidmq.queue")
NODE_ROUTING_KEY = os.getenv("RABBITMQ_NODE_ROUTING_KEY", "rapidmq.node")

OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "rapidmq-python")


def setup_otel() -> None:
    resource = Resource.create({RESOURCE_SERVICE_NAME: SERVICE_NAME})

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=OTEL_ENDPOINT))
    )
    trace.set_tracer_provider(tracer_provider)

    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=OTEL_ENDPOINT),
        export_interval_millis=10000,
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(
        BatchLogRecordProcessor(OTLPLogExporter(endpoint=OTEL_ENDPOINT))
    )
    set_logger_provider(logger_provider)
    logging.getLogger().addHandler(LoggingHandler(logger_provider=logger_provider))


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)

setup_otel()

tracer = trace.get_tracer("rapidmq-python")
meter = metrics.get_meter("rapidmq-python")
messages_consumed = meter.create_counter(
    "rapidmq.messages.consumed",
    description="Messages consumed from RabbitMQ",
)
messages_forwarded = meter.create_counter(
    "rapidmq.messages.forwarded",
    description="Messages forwarded to node queue",
)

connection = None
channel = None
publish_exchange = None


async def connect_rabbitmq() -> None:
    global connection, channel, publish_exchange

    vhost = urllib.parse.quote(RABBITMQ_VHOST, safe="")
    url = f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASS}@{RABBITMQ_HOST}:{RABBITMQ_PORT}/{vhost}"

    connection = await aio_pika.connect_robust(url)
    channel = await connection.channel()

    publish_exchange = await channel.declare_exchange(EXCHANGE, aio_pika.ExchangeType.DIRECT, durable=True)
    queue = await channel.declare_queue(QUEUE, durable=True)
    await queue.bind(publish_exchange, ROUTING_KEY)


async def consume_loop() -> None:
    queue = await channel.get_queue(QUEUE)

    async with queue.iterator() as queue_iter:
        async for message in queue_iter:
            async with message.process():
                carrier = dict(message.headers or {})
                ctx = propagate.extract(carrier)

                with tracer.start_as_current_span(
                    "rabbitmq.consume",
                    context=ctx,
                    kind=SpanKind.CONSUMER,
                    attributes={
                        "messaging.system": "rabbitmq",
                        "messaging.destination": QUEUE,
                        "messaging.operation": "receive",
                    },
                ):
                    body = message.body.decode()
                    logging.info("Consumed message: %s", body)
                    messages_consumed.add(1)

                    forward_headers: dict = {}
                    propagate.inject(forward_headers)

                    forward_msg = aio_pika.Message(body=message.body, headers=forward_headers)
                    await publish_exchange.publish(forward_msg, routing_key=NODE_ROUTING_KEY)
                    messages_forwarded.add(1)
                    logging.info("Forwarded message to node queue")


async def main() -> None:
    logging.info("Starting RapidMQ Python service")
    await connect_rabbitmq()
    logging.info("Connected to RabbitMQ at %s:%d", RABBITMQ_HOST, RABBITMQ_PORT)
    asyncio.create_task(consume_loop())
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
