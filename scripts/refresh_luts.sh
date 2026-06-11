#!/usr/bin/env bash
# Monthly re-validation of the gate LUTs on fresh data (markets drift).
# Re-runs the three OOS+stability backtests and commits the updated LUTs
# locally (no push — review before sharing).
#
# NOTE: crypto setups refresh from live Binance data each run. Stock setups
# read the cached OHLC (python/data/ohlc_cache) + the historical signal grid,
# which are static snapshots — to fully refresh stocks, regenerate those first
# (Tiingo-rate-limited). The flat baseline reads the grid trades parquet.
set +e
cd /Users/DEV/Elliott-wave || exit 1
PY=.venv/bin/python
LOG=brain-output/lut_refresh.log

{
  echo "==================== LUT refresh $(date) ===================="
  EWB_WAVE3=1 "$PY" python/scripts/backtest_wave3.py
  "$PY" python/scripts/backtest_core_setups.py
  "$PY" python/scripts/backtest_ewb_strategy.py --tp-mult 1.618 --sl-mult 1.0
  "$PY" python/scripts/backtest_htf_flat.py
} >>"$LOG" 2>&1

git add brain-output/backtests/ewb_strategy_backtest_grouped.parquet \
        brain-output/backtests/ewb_wave3_backtest_grouped.parquet \
        brain-output/backtests/ewb_core_backtest_grouped.parquet \
        brain-output/backtests/ewb_htf_flat_backtest_grouped.parquet 2>>"$LOG"

if git diff --cached --quiet; then
  echo "$(date): LUTs unchanged — nothing to commit" >>"$LOG"
else
  git commit -q -m "Auto LUT refresh $(date +%F)" \
    -m "Monthly re-validation of gate setups (OOS+stability) on fresh data." \
    -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>" >>"$LOG" 2>&1
  echo "$(date): LUTs refreshed and committed (review + push manually)" >>"$LOG"
fi
