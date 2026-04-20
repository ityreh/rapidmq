#!/usr/bin/env bash
set -euo pipefail

kubectl -n rabbitmq port-forward svc/rabbitmq 15672:15672
