#!/usr/bin/env bash
set -euo pipefail

cd "/Users/DEV/Elliott-wave"
mkdir -p "brain-output/backtests/logs"

PYTHON_BIN="${PYTHON_BIN:-}"
if [ -z "$PYTHON_BIN" ]; then
  if [ -x ".venv/bin/python" ]; then
    PYTHON_BIN=".venv/bin/python"
  else
    PYTHON_BIN="python3"
  fi
fi

{
  echo "=== $(date -u '+%Y-%m-%dT%H:%M:%SZ') strategy_system start ==="
  "$PYTHON_BIN" python/scripts/backtest_ewb_strategy.py --asset-class both --intervals 1h 4h 1d 1w
  "$PYTHON_BIN" python/scripts/forward_daily_report.py
  "$PYTHON_BIN" python/scripts/compare_backtest_forward.py
  echo "=== $(date -u '+%Y-%m-%dT%H:%M:%SZ') strategy_system done ==="
} >> "brain-output/backtests/logs/strategy_system.log" 2>&1
