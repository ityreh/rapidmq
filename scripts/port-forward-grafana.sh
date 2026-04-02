#!/usr/bin/env bash
set -euo pipefail

kubectl -n observability port-forward svc/grafana 3000:80
