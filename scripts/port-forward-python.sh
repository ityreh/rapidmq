#!/usr/bin/env bash
set -euo pipefail

kubectl -n services port-forward svc/rapidmq-python 8082:8082
