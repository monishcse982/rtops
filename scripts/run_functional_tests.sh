#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

echo "Running functional tests..."
pytest tests/e2e "$@"

echo "Publishing functional report artifacts..."
python3 scripts/publish_reports.py functional
