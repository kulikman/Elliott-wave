# Crypto Pine/Python Parity Review

Generated: `2026-06-05`

## Scope

- Universe: top20 crypto research universe with `TRX-USD` instead of legacy `MATIC-USD`.
- Data source: Binance spot klines from `python/scripts/historical_signal_grid.py`.
- Trade rows: `235649`.
- Canonical calibration rows: `1983`.
- Production decision: crypto remains research-only.

## Findings

### High - Crypto still cannot be production BUY/SELL

Files:
- `pine/ewb_monowaves_mtf.pine`
- `pine/ewb_probability_overlay_v0.pine`
- `brain-output/indicator-spec/probability_calibration_crypto_v0.json`

Reason:
The new crypto grid has attractive-looking pockets, especially `double_corr`
on intraday timeframes, but several of the strongest rows still have low sample
confidence or narrow setup definitions. The production indicator must not turn
those into actionable signals for Anton until TradingView parity and venue
checks pass.

Minimal fix:
Keep crypto `Action now = WAIT`, show `crypto-v0 research`, and disable BUY/SELL
alerts on crypto charts.

### Medium - Best-looking setups are research candidates, not defaults

Current candidates from `docs/validation/historical_signal_grid_crypto_report.md`:

| Setup | Observation | Decision |
|---|---|---|
| `15m double_corr short` | high winrate in grid, medium confidence, small-ish sample | research candidate only |
| `1h flat short` | balanced row has positive test EV and high confidence | research candidate only |
| `4h flat long` | positive EV but test winrate is weak | research candidate only |
| `impulse / triangle` | large drawdowns or unstable OOS behavior | keep WAIT/context |

### Medium - Overlay could visually imply stock probability on crypto

File:
- `pine/ewb_probability_overlay_v0.pine`

Reason:
Even when alerts were blocked, the overlay panel could display stock-calibrated
P/EV and Entry/Stop/TP fields for crypto charts. That can look like a trade plan.

Minimal fix:
On crypto/unsupported charts, the overlay panel now hides P/EV, confidence,
R:R, Entry, Stop and TP fields, while the market row shows `crypto-v0 research`.

## Pine Contract

Main indicator:
- `Market mode = Stocks`: production mode for stocks only.
- `Market mode = Auto`: stocks can be actionable, crypto remains research-only.
- `Market mode = Crypto`: crypto research view only.
- `Market mode = Research any`: manual research view; crypto remains WAIT.

Probability overlay:
- Remains a research overlay, not the main Action source.
- `Enable research Action/alerts` defaults to off.
- Crypto charts stay `WAIT / crypto research only`.
- No legacy `Any` market mode.

## Current Decision

Do not enable crypto BUY/SELL yet.

Before promotion, run:

1. Manual TradingView parity on BTCUSDT, ETHUSDT, SOLUSDT and TRXUSDT.
2. Venue comparison: Binance spot vs the exact TradingView symbol/exchange.
3. Pine/Python comparison for pattern, side, confirmation bar, Entry, SL, TP and reason.
4. Separate crypto alert dry-run with `enableActions = false` by default.
5. A production review that promotes only specific setup/timeframe/side combinations.

## Files

- `python/data/historical_signal_grid_crypto_trades.parquet`
- `brain-output/indicator-spec/probability_calibration_crypto_v0.json`
- `brain-output/signals/historical_signal_grid_crypto_summary.json`
- `docs/pine_parity_crypto_checklist.md`
- `pine/ewb_monowaves_mtf.pine`
- `pine/ewb_probability_overlay_v0.pine`
