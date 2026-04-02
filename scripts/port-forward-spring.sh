#!/usr/bin/env bash
set -euo pipefail

kubectl -n services port-forward svc/rapidmq-spring 8081:8081
