#!/usr/bin/env bash
set -euo pipefail

cd "/Users/DEV/Elliott-wave"
mkdir -p "brain-output/signals/logs"

PYTHON_BIN="${PYTHON_BIN:-}"
if [ -z "$PYTHON_BIN" ]; then
  if [ -x ".venv/bin/python" ]; then
    PYTHON_BIN=".venv/bin/python"
  else
    PYTHON_BIN="python3"
  fi
fi

{
  echo "=== $(date -u '+%Y-%m-%dT%H:%M:%SZ') daily_report start ==="
  "$PYTHON_BIN" python/scripts/daily_report.py
  echo "=== $(date -u '+%Y-%m-%dT%H:%M:%SZ') daily_report done ==="
} >> "brain-output/signals/logs/daily_report.log" 2>&1
