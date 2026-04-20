#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

kubectl apply -f "$ROOT_DIR/k8s/namespaces.yaml"

helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo add grafana https://grafana.github.io/helm-charts
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm repo update

helm upgrade --install rabbitmq-cluster-operator bitnami/rabbitmq-cluster-operator \
  -n rabbitmq-system \
  --set clusterOperator.image.registry=ghcr.io \
  --set clusterOperator.image.repository=rabbitmq/cluster-operator \
  --set clusterOperator.image.tag=latest \
  --set 'clusterOperator.command={/manager}' \
  --set clusterOperator.readinessProbe.enabled=false \
  --set clusterOperator.livenessProbe.enabled=false \
  --set clusterOperator.resources.requests.cpu=100m \
  --set clusterOperator.resources.requests.memory=128Mi \
  --set clusterOperator.resources.limits.cpu=500m \
  --set clusterOperator.resources.limits.memory=256Mi \
  --set msgTopologyOperator.image.registry=ghcr.io \
  --set msgTopologyOperator.image.repository=rabbitmq/messaging-topology-operator \
  --set msgTopologyOperator.image.tag=latest \
  --set 'msgTopologyOperator.command={/manager}' \
  --set msgTopologyOperator.readinessProbe.enabled=false \
  --set msgTopologyOperator.livenessProbe.enabled=false \
  --set msgTopologyOperator.resources.requests.cpu=100m \
  --set msgTopologyOperator.resources.requests.memory=128Mi \
  --set msgTopologyOperator.resources.limits.cpu=500m \
  --set msgTopologyOperator.resources.limits.memory=256Mi \
  --set global.security.allowInsecureImages=true

kubectl rollout status deployment \
  rabbitmq-cluster-operator \
  rabbitmq-cluster-operator-rabbitmq-messaging-topology-operator \
  -n rabbitmq-system --timeout=10m

# The ghcr.io upstream image requires EndpointSlice access not included in the Bitnami chart's RBAC
kubectl apply -f "$ROOT_DIR/k8s/rabbitmq/operator-rbac-patch.yaml"

kubectl apply -f "$ROOT_DIR/k8s/rabbitmq/cluster.yaml"

kubectl wait rabbitmqcluster rabbitmq -n rabbitmq \
  --for=condition=AllReplicasReady --timeout=10m

kubectl apply -f "$ROOT_DIR/k8s/rabbitmq/topology.yaml"

kubectl wait rabbitmquser app -n rabbitmq \
  --for=condition=Ready --timeout=5m
kubectl wait rabbitmqpermission app-rapidmq -n rabbitmq \
  --for=condition=Ready --timeout=5m

helm upgrade --install mimir grafana/mimir-distributed \
  -n observability -f "$ROOT_DIR/k8s/observability/mimir-values.yaml"

helm upgrade --install loki grafana/loki \
  -n observability -f "$ROOT_DIR/k8s/observability/loki-values.yaml"

helm upgrade --install tempo grafana/tempo \
  -n observability -f "$ROOT_DIR/k8s/observability/tempo-values.yaml"

helm upgrade --install grafana grafana/grafana \
  -n observability -f "$ROOT_DIR/k8s/observability/grafana-values.yaml"

helm upgrade --install otel-collector open-telemetry/opentelemetry-collector \
  -n observability -f "$ROOT_DIR/k8s/observability/otel-collector-values.yaml"

kubectl rollout status deployment otel-collector-opentelemetry-collector \
  -n observability --timeout=5m

# Build service images into Minikube's Docker daemon
"$ROOT_DIR/scripts/build-images.sh"

kubectl apply -f "$ROOT_DIR/k8s/services/springboot.yaml"
kubectl apply -f "$ROOT_DIR/k8s/services/python.yaml"
kubectl apply -f "$ROOT_DIR/k8s/services/node.yaml"
