#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

echo "Pointing Docker at Minikube's daemon..."
eval "$(minikube docker-env)"

echo "Building rapidmq-spring:local..."
docker build -t rapidmq-spring:local "$ROOT_DIR/services/springboot"

echo "Building rapidmq-python:local..."
docker build -t rapidmq-python:local "$ROOT_DIR/services/python"

echo "Building rapidmq-node:local..."
docker build -t rapidmq-node:local "$ROOT_DIR/services/node"

echo "All images built."
