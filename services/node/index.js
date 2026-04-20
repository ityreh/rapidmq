const express = require("express");
const amqp = require("amqplib");
const {
  context,
  propagation,
  trace,
  SpanKind,
} = require("@opentelemetry/api");
const { logs } = require("@opentelemetry/api-logs");
const { NodeSDK } = require("@opentelemetry/sdk-node");
const { Resource } = require("@opentelemetry/resources");
const { BatchLogRecordProcessor } = require("@opentelemetry/sdk-logs");
const {
  OTLPTraceExporter,
} = require("@opentelemetry/exporter-trace-otlp-grpc");
const {
  OTLPMetricExporter,
} = require("@opentelemetry/exporter-metrics-otlp-grpc");
const {
  OTLPLogExporter,
} = require("@opentelemetry/exporter-logs-otlp-grpc");
const {
  PeriodicExportingMetricReader,
} = require("@opentelemetry/sdk-metrics");
const {
  HttpInstrumentation,
} = require("@opentelemetry/instrumentation-http");
const {
  ExpressInstrumentation,
} = require("@opentelemetry/instrumentation-express");

const RABBITMQ_HOST = process.env.RABBITMQ_HOST || "localhost";
const RABBITMQ_PORT = process.env.RABBITMQ_PORT || "5672";
const RABBITMQ_USER = process.env.RABBITMQ_USER || "app";
const RABBITMQ_PASS = process.env.RABBITMQ_PASS || "app";
const RABBITMQ_VHOST = process.env.RABBITMQ_VHOST || "/rapidmq";

const EXCHANGE = "rapidmq.exchange";
// Node consumes from its own queue bound to "rapidmq.node" routing key
const QUEUE = process.env.RABBITMQ_QUEUE || "rapidmq.queue.node";
const CONSUME_ROUTING_KEY = process.env.RABBITMQ_CONSUME_ROUTING_KEY || "rapidmq.node";
// Node's /publish endpoint sends to the main queue to trigger the full chain
const PUBLISH_ROUTING_KEY = process.env.RABBITMQ_PUBLISH_ROUTING_KEY || "rapidmq.key";

const OTEL_ENDPOINT = process.env.OTEL_EXPORTER_OTLP_ENDPOINT || "http://localhost:4317";
const SERVICE_NAME = process.env.OTEL_SERVICE_NAME || "rapidmq-node";

const resource = new Resource({ "service.name": SERVICE_NAME });

const traceExporter = new OTLPTraceExporter({
  url: OTEL_ENDPOINT,
});

const metricReader = new PeriodicExportingMetricReader({
  exporter: new OTLPMetricExporter({ url: OTEL_ENDPOINT }),
  exportIntervalMillis: 10000,
});

const logExporter = new OTLPLogExporter({
  url: OTEL_ENDPOINT,
});

const logProcessor = new BatchLogRecordProcessor(logExporter);

const sdk = new NodeSDK({
  resource,
  traceExporter,
  metricReader,
  logRecordProcessor: logProcessor,
  instrumentations: [
    new HttpInstrumentation(),
    new ExpressInstrumentation(),
  ],
});

async function start() {
  await sdk.start();
  // Logger must be obtained after sdk.start() — calling logs.getLogger() before
  // start() captures the noop LoggerProvider and never exports anything.
  const logger = logs.getLogger("rapidmq-node");

  const encodedVhost = encodeURIComponent(RABBITMQ_VHOST);
  const amqpUrl = `amqp://${RABBITMQ_USER}:${RABBITMQ_PASS}@${RABBITMQ_HOST}:${RABBITMQ_PORT}/${encodedVhost}`;
  const connection = await amqp.connect(amqpUrl);
  const channel = await connection.createChannel();

  await channel.assertExchange(EXCHANGE, "direct", { durable: true });
  await channel.assertQueue(QUEUE, { durable: true });
  await channel.bindQueue(QUEUE, EXCHANGE, CONSUME_ROUTING_KEY);

  channel.consume(QUEUE, (msg) => {
    if (!msg) return;

    const headers = msg.properties.headers || {};
    const extractedContext = propagation.extract(context.active(), headers);

    const tracer = trace.getTracer("rapidmq-node");
    context.with(extractedContext, () => {
      const span = tracer.startSpan("rabbitmq.consume", { kind: SpanKind.CONSUMER });
      span.addEvent("message.received");

      const body = msg.content.toString();
      logger.emit({ body: `Consumed message: ${body}` });

      span.end();
      channel.ack(msg);
    });
  });

  const app = express();
  app.use(express.json());

  app.post("/publish", async (req, res) => {
    const message = req.body?.message || "hello";
    const tracer = trace.getTracer("rapidmq-node");

    const span = tracer.startSpan("rabbitmq.publish", { kind: SpanKind.PRODUCER });
    await context.with(trace.setSpan(context.active(), span), async () => {
      const headers = {};
      propagation.inject(context.active(), headers);

      channel.publish(EXCHANGE, PUBLISH_ROUTING_KEY, Buffer.from(message), {
        headers,
      });

      logger.emit({ body: `Published message: ${message}` });
      span.end();
      res.json({ status: "ok", message });
    });
  });

  app.listen(8083, () => {
    // Server ready
  });
}

start().catch((err) => {
  // eslint-disable-next-line no-console
  console.error(err);
  process.exit(1);
});
