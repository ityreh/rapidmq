# Architecture

## Components

- RabbitMQ Cluster Operator and Topology Operator
- RabbitMQCluster plus topology resources (vhost, user, permissions, exchange, queue, binding)
- Grafana, Mimir, Tempo, Loki
- OpenTelemetry Collector as a shared OTLP ingress
- Three services (Spring Boot, Python uv, Node)

## Data Flow

1. Services publish/consume RabbitMQ messages.
2. Trace context is injected into AMQP headers.
3. Services emit OTLP traces/metrics/logs to the Collector.
4. Collector exports:
   - traces -> Tempo
   - metrics -> Mimir (remote write)
   - logs -> Loki
5. Grafana reads from Tempo/Loki/Mimir.

## Namespaces

- rabbitmq-system: operators
- rabbitmq: RabbitMQCluster and topology
- observability: Grafana, Mimir, Tempo, Loki, OTel Collector
- services: sample apps
