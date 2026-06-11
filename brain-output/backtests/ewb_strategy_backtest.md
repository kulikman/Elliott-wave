# EWB Strategy System Backtest

This report tests the bot contract around the TradingView indicator. Pine remains the visual/alert surface; this report is the statistical control surface.

## Contract

- Strategy: `ewb-anton-v1`
- Entry rule: `confirm_close_or_alert_close`
- Exit rule: `tp_sl_time`
- Patterns: `flat, double_corr`
- Intervals: `1h, 4h, 1d, 1w`
- Filters: min model P `55.0%`, min sample `20`, universe rank <= `100`
- Canonical slice: entry `confirm_close`, MTF `none`, late `999.0`, TP `1.618`, SL `1.0`, exit `full`

## Portfolio Summary

| Trades | Win | Exp | PF | DD | Total |
|---|---|---|---|---|---|
| 1518 | 56.8% | 1.77% | 1.96 | -97.5% | 3860653557.3% |

## By Asset / TF / Pattern

| Asset | TF | Pattern | Side | Trades | Win | Exp | PF | DD |
|---|---|---|---|---|---|---|---|---|
| crypto | 1w | flat | long | 7 | 57.1% | 51.98% | 7.54 | -42.2% |
| stock | 1w | flat | long | 67 | 71.6% | 11.72% | 6.51 | -40.6% |
| stock | 1d | flat | long | 82 | 65.9% | 3.99% | 3.78 | -30.1% |
| stock | 4h | flat | long | 147 | 59.2% | 1.97% | 2.92 | -37.8% |
| stock | 1h | flat | long | 444 | 59.0% | 1.02% | 2.65 | -24.6% |
| crypto | 1d | flat | short | 27 | 70.4% | 5.12% | 2.16 | -69.0% |
| crypto | 4h | flat | short | 132 | 65.9% | 1.31% | 1.80 | -42.6% |
| crypto | 4h | flat | long | 111 | 54.1% | 1.62% | 1.78 | -59.2% |
| crypto | 1d | flat | long | 26 | 53.8% | 6.26% | 1.71 | -74.6% |
| crypto | 1h | flat | long | 226 | 51.3% | 0.24% | 1.25 | -24.9% |
| stock | 4h | flat | short | 127 | 48.0% | 0.29% | 1.18 | -27.6% |
| crypto | 1w | flat | short | 10 | 60.0% | 2.20% | 1.09 | -97.9% |
| stock | 1d | flat | short | 76 | 43.4% | -0.13% | 0.95 | -72.9% |
| stock | 1w | flat | short | 36 | 30.6% | -7.91% | 0.26 | -96.9% |

## Best Setup Keys

| Setup | Trades | Win | Exp | PF | DD |
|---|---|---|---|---|---|
| crypto|1w|flat|long|none|confirm_close | 7 | 57.1% | 51.98% | 7.54 | -42.2% |
| stock|1w|flat|long|none|confirm_close | 67 | 71.6% | 11.72% | 6.51 | -40.6% |
| stock|1d|flat|long|none|confirm_close | 82 | 65.9% | 3.99% | 3.78 | -30.1% |
| stock|4h|flat|long|none|confirm_close | 147 | 59.2% | 1.97% | 2.92 | -37.8% |
| stock|1h|flat|long|none|confirm_close | 444 | 59.0% | 1.02% | 2.65 | -24.6% |
| crypto|1d|flat|short|none|confirm_close | 27 | 70.4% | 5.12% | 2.16 | -69.0% |
| crypto|4h|flat|short|none|confirm_close | 132 | 65.9% | 1.31% | 1.80 | -42.6% |
| crypto|4h|flat|long|none|confirm_close | 111 | 54.1% | 1.62% | 1.78 | -59.2% |
| crypto|1d|flat|long|none|confirm_close | 26 | 53.8% | 6.26% | 1.71 | -74.6% |
| crypto|1h|flat|long|none|confirm_close | 226 | 51.3% | 0.24% | 1.25 | -24.9% |
| stock|4h|flat|short|none|confirm_close | 127 | 48.0% | 0.29% | 1.18 | -27.6% |
| crypto|1w|flat|short|none|confirm_close | 10 | 60.0% | 2.20% | 1.09 | -97.9% |
| stock|1d|flat|short|none|confirm_close | 76 | 43.4% | -0.13% | 0.95 | -72.9% |
| stock|1w|flat|short|none|confirm_close | 36 | 30.6% | -7.91% | 0.26 | -96.9% |

## Walk Forward Folds

| Fold | Start | End | Trades | Win | Exp | PF | DD |
|---|---|---|---|---|---|---|---|
| 1 | 2017-01-09T00:00:00+00:00 | 2023-10-13T16:00:00+00:00 | 253 | 60.1% | 3.79% | 2.12 | -97.5% |
| 2 | 2023-10-15T00:00:00+00:00 | 2024-06-11T12:00:00+00:00 | 253 | 58.1% | 1.58% | 2.17 | -51.6% |
| 3 | 2024-06-11T17:30:00+00:00 | 2024-12-23T03:00:00+00:00 | 253 | 60.5% | 1.75% | 2.61 | -30.0% |
| 4 | 2024-12-23T14:30:00+00:00 | 2025-07-08T17:00:00+00:00 | 253 | 56.9% | 1.31% | 1.87 | -82.9% |
| 5 | 2025-07-09T04:00:00+00:00 | 2026-01-15T00:00:00+00:00 | 253 | 53.0% | 1.24% | 1.69 | -53.2% |
| 6 | 2026-01-15T14:30:00+00:00 | 2026-06-05T04:00:00+00:00 | 253 | 52.2% | 0.97% | 1.49 | -81.2% |

## How To Use

- Use this as the historical baseline before turning on a bot.
- Then run `forward_signal_logger.py add` for every alert and `settle` for every exit.
- Compare live forward trades with this baseline using `compare_backtest_forward.py`.
- Do not optimize against the forward log; it is the reality check.
