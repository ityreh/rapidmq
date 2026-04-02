#!/usr/bin/env bash
set -euo pipefail

kubectl -n services port-forward svc/rapidmq-node 8083:8083
