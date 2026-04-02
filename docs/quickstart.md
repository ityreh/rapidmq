# Quickstart

## 1) Start Minikube

```bash
./scripts/minikube-start.sh
eval "$(minikube docker-env)"
docker build -t rapidmq-spring:local services/springboot
docker build -t rapidmq-python:local services/python
docker build -t rapidmq-node:local services/node
```

## 2) Deploy operators, observability, and apps

```bash
./scripts/bootstrap.sh
```

## 3) Access Grafana

```bash
./scripts/port-forward-grafana.sh
```

Open http://localhost:3000.

## 4) Send a test message

```bash
./scripts/port-forward-spring.sh
curl -X POST http://localhost:8081/publish -H 'content-type: application/json' -d '{"message":"hello"}'
```

## 5) Verify

- RabbitMQ pods are Ready.
- Tempo shows traces for producer and consumer spans.
- Loki shows app logs with trace IDs.
- Mimir has basic service metrics.

## Common Commands

```bash
kubectl get pods -A
kubectl get rabbitmqclusters -n rabbitmq
kubectl get queues -n rabbitmq
```
