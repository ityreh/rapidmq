#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="$1"
LABEL_SELECTOR="$2"
TIMEOUT_SECONDS="${3:-300}"

end=$((SECONDS + TIMEOUT_SECONDS))

while [[ $SECONDS -lt $end ]]; do
  ready=$(kubectl -n "$NAMESPACE" get pods -l "$LABEL_SELECTOR" -o jsonpath='{.items[*].status.containerStatuses[*].ready}' 2>/dev/null | tr ' ' '\n' | grep -c true || true)
  total=$(kubectl -n "$NAMESPACE" get pods -l "$LABEL_SELECTOR" -o jsonpath='{.items[*].status.containerStatuses[*].ready}' 2>/dev/null | tr ' ' '\n' | wc -l | tr -d ' ' || true)
  if [[ "$total" -gt 0 && "$ready" -eq "$total" ]]; then
    echo "Ready: $NAMESPACE $LABEL_SELECTOR"
    exit 0
  fi
  sleep 5
 done

echo "Timeout waiting for $NAMESPACE $LABEL_SELECTOR"
exit 1
