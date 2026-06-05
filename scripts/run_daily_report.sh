#!/usr/bin/env bash
set -euo pipefail

cd "/Users/DEV/Elliott-wave"
mkdir -p "brain-output/signals/logs"

{
  echo "=== $(date -u '+%Y-%m-%dT%H:%M:%SZ') daily_report start ==="
  python3 python/scripts/daily_report.py
  echo "=== $(date -u '+%Y-%m-%dT%H:%M:%SZ') daily_report done ==="
} >> "brain-output/signals/logs/daily_report.log" 2>&1
