#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

LOCUST_CONFIG="${LOCUST_CONFIG:-tests/perf/locust.local.conf}"
LOCUST_HOST="${LOCUST_HOST:-http://localhost:8000}"
LOCUST_USERS="${LOCUST_USERS:-10}"
LOCUST_SPAWN_RATE="${LOCUST_SPAWN_RATE:-2}"
LOCUST_RUN_TIME="${LOCUST_RUN_TIME:-1m}"

if [ "$#" -gt 0 ]; then
  echo "Running performance tests with custom Locust arguments..."
  uv run locust "$@"
else
  echo "Running performance tests..."
  uv run locust \
    --config "${LOCUST_CONFIG}" \
    --host "${LOCUST_HOST}" \
    --headless \
    -u "${LOCUST_USERS}" \
    -r "${LOCUST_SPAWN_RATE}" \
    -t "${LOCUST_RUN_TIME}"
fi

echo "Performance report artifacts are available under reports/locust."
