#!/usr/bin/env bash
set -euo pipefail

cd "/Users/DEV/Elliott-wave"
mkdir -p "brain-output/backtests/logs"

{
  echo "=== $(date -u '+%Y-%m-%dT%H:%M:%SZ') strategy_system start ==="
  python3 python/scripts/backtest_ewb_strategy.py --asset-class both --intervals 1h 4h 1d 1w
  python3 python/scripts/forward_daily_report.py
  python3 python/scripts/compare_backtest_forward.py
  echo "=== $(date -u '+%Y-%m-%dT%H:%M:%SZ') strategy_system done ==="
} >> "brain-output/backtests/logs/strategy_system.log" 2>&1
