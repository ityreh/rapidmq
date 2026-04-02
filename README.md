# RapidMQ Local Stack

Local Minikube playground for RabbitMQ (Bitnami Helm chart), Grafana observability (Mimir, Tempo, Loki), and three sample services (Spring Boot, Python uv, Node) with OpenTelemetry context propagation and OTLP export.

## Prerequisites

- minikube
- kubectl
- helm
- docker

## Quickstart

```bash
./scripts/minikube-start.sh
eval "$(minikube docker-env)"
docker build -t rapidmq-spring:local services/springboot
docker build -t rapidmq-python:local services/python
docker build -t rapidmq-node:local services/node
./scripts/bootstrap.sh
./scripts/port-forward-grafana.sh
```

Then open Grafana at http://localhost:3000 (anonymous access enabled).

To send a test message:

```bash
./scripts/port-forward-spring.sh
curl -X POST http://localhost:8081/publish -H 'content-type: application/json' -d '{"message":"hello"}'
```

## Sample Flow

- Spring Boot exposes `POST /publish` to send a message.
- Python and Node services both include a consumer and an HTTP endpoint to publish.
- Trace context is injected into RabbitMQ headers and extracted by consumers.
- All services export traces/metrics/logs to the OpenTelemetry Collector via OTLP.

## Repository Layout

- docs/: architecture and troubleshooting notes
- scripts/: minikube and deployment helpers
- k8s/: Kubernetes and Helm values
- services/: example applications

## Teardown

```bash
./scripts/teardown.sh
./scripts/minikube-stop.sh
```

## Notes

- Uses default Minikube profile and latest stable Helm charts.
- If your machine is resource constrained, reduce replicas in the values files.
- If scripts are not executable, run `chmod +x scripts/*.sh`.
