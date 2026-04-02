#!/usr/bin/env bash
set -euo pipefail

helm -n observability uninstall grafana || true
helm -n observability uninstall tempo || true
helm -n observability uninstall loki || true
helm -n observability uninstall mimir || true
helm -n observability uninstall otel-collector || true

kubectl delete -f "$(dirname "$0")/../k8s/services" || true
kubectl delete -f "$(dirname "$0")/../k8s/rabbitmq/topology.yaml" || true
kubectl delete -f "$(dirname "$0")/../k8s/rabbitmq/cluster.yaml" || true

helm -n rabbitmq-system uninstall rabbitmq-cluster-operator || true
