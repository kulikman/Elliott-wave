# EWB Strategy System Backtest

This report tests the bot contract around the TradingView indicator. Pine remains the visual/alert surface; this report is the statistical control surface.

## Contract

- Strategy: `ewb-anton-v1`
- Entry rule: `confirm_close_or_alert_close`
- Exit rule: `tp_sl_time`
- Patterns: `flat, double_corr`
- Intervals: `1h, 4h, 1d, 1w`
- Filters: min model P `55.0%`, min sample `20`, universe rank <= `100`
- Canonical slice: entry `confirm_close`, MTF `none`, late `999.0`, TP `1.0`, SL `1.0`, exit `full`

## Portfolio Summary

| Trades | Win | Exp | PF | DD | Total |
|---|---|---|---|---|---|
| 1518 | 59.9% | 1.44% | 1.83 | -96.2% | 160205313.5% |

## By Asset / TF / Pattern

| Asset | TF | Pattern | Side | Trades | Win | Exp | PF | DD |
|---|---|---|---|---|---|---|---|---|
| stock | 1w | flat | long | 67 | 74.6% | 9.86% | 6.07 | -37.7% |
| crypto | 1w | flat | long | 7 | 57.1% | 29.03% | 4.65 | -42.2% |
| stock | 1d | flat | long | 82 | 70.7% | 3.25% | 3.43 | -30.1% |
| stock | 4h | flat | long | 147 | 61.9% | 1.44% | 2.48 | -37.3% |
| stock | 1h | flat | long | 444 | 62.2% | 0.82% | 2.40 | -22.7% |
| crypto | 4h | flat | long | 111 | 58.6% | 2.06% | 2.11 | -43.9% |
| crypto | 1d | flat | short | 27 | 70.4% | 4.06% | 1.92 | -66.8% |
| crypto | 4h | flat | short | 132 | 69.7% | 1.27% | 1.82 | -44.7% |
| crypto | 1w | flat | short | 10 | 70.0% | 11.11% | 1.58 | -97.9% |
| crypto | 1d | flat | long | 26 | 53.8% | 3.46% | 1.39 | -79.3% |
| crypto | 1h | flat | long | 226 | 54.4% | 0.18% | 1.20 | -24.7% |
| stock | 4h | flat | short | 127 | 49.6% | 0.10% | 1.06 | -30.4% |
| stock | 1d | flat | short | 76 | 47.4% | 0.14% | 1.05 | -62.8% |
| stock | 1w | flat | short | 36 | 30.6% | -8.18% | 0.24 | -97.2% |

## Best Setup Keys

| Setup | Trades | Win | Exp | PF | DD |
|---|---|---|---|---|---|
| stock|1w|flat|long|none|confirm_close | 67 | 74.6% | 9.86% | 6.07 | -37.7% |
| crypto|1w|flat|long|none|confirm_close | 7 | 57.1% | 29.03% | 4.65 | -42.2% |
| stock|1d|flat|long|none|confirm_close | 82 | 70.7% | 3.25% | 3.43 | -30.1% |
| stock|4h|flat|long|none|confirm_close | 147 | 61.9% | 1.44% | 2.48 | -37.3% |
| stock|1h|flat|long|none|confirm_close | 444 | 62.2% | 0.82% | 2.40 | -22.7% |
| crypto|4h|flat|long|none|confirm_close | 111 | 58.6% | 2.06% | 2.11 | -43.9% |
| crypto|1d|flat|short|none|confirm_close | 27 | 70.4% | 4.06% | 1.92 | -66.8% |
| crypto|4h|flat|short|none|confirm_close | 132 | 69.7% | 1.27% | 1.82 | -44.7% |
| crypto|1w|flat|short|none|confirm_close | 10 | 70.0% | 11.11% | 1.58 | -97.9% |
| crypto|1d|flat|long|none|confirm_close | 26 | 53.8% | 3.46% | 1.39 | -79.3% |
| crypto|1h|flat|long|none|confirm_close | 226 | 54.4% | 0.18% | 1.20 | -24.7% |
| stock|4h|flat|short|none|confirm_close | 127 | 49.6% | 0.10% | 1.06 | -30.4% |
| stock|1d|flat|short|none|confirm_close | 76 | 47.4% | 0.14% | 1.05 | -62.8% |
| stock|1w|flat|short|none|confirm_close | 36 | 30.6% | -8.18% | 0.24 | -97.2% |

## Walk Forward Folds

| Fold | Start | End | Trades | Win | Exp | PF | DD |
|---|---|---|---|---|---|---|---|
| 1 | 2017-01-09T00:00:00+00:00 | 2023-10-13T16:00:00+00:00 | 253 | 63.6% | 3.28% | 2.06 | -96.2% |
| 2 | 2023-10-15T00:00:00+00:00 | 2024-06-11T12:00:00+00:00 | 253 | 59.7% | 1.21% | 1.96 | -44.0% |
| 3 | 2024-06-11T17:30:00+00:00 | 2024-12-23T03:00:00+00:00 | 253 | 63.2% | 1.38% | 2.34 | -30.0% |
| 4 | 2024-12-23T14:30:00+00:00 | 2025-07-08T17:00:00+00:00 | 253 | 60.1% | 1.17% | 1.80 | -81.7% |
| 5 | 2025-07-09T04:00:00+00:00 | 2026-01-15T00:00:00+00:00 | 253 | 58.1% | 1.12% | 1.67 | -54.3% |
| 6 | 2026-01-15T14:30:00+00:00 | 2026-06-05T04:00:00+00:00 | 253 | 54.5% | 0.48% | 1.25 | -82.6% |

## How To Use

- Use this as the historical baseline before turning on a bot.
- Then run `forward_signal_logger.py add` for every alert and `settle` for every exit.
- Compare live forward trades with this baseline using `compare_backtest_forward.py`.
- Do not optimize against the forward log; it is the reality check.
