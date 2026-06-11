# EWB Strategy System Backtest

This report tests the bot contract around the TradingView indicator. Pine remains the visual/alert surface; this report is the statistical control surface.

## Contract

- Strategy: `ewb-anton-v1`
- Entry rule: `confirm_close_or_alert_close`
- Exit rule: `tp_sl_time`
- Patterns: `flat, double_corr`
- Intervals: `1h, 4h, 1d, 1w`
- Filters: min model P `55.0%`, min sample `20`, universe rank <= `100`
- Canonical slice: entry `next_open, next_bar_open`, MTF `none`, late `999.0`, TP `1.618`, SL `1.0`, exit `full`

## Portfolio Summary

| Trades | Win | Exp | PF | DD | Total |
|---|---|---|---|---|---|
| 1512 | 57.5% | 1.85% | 1.97 | -98.6% | 5907772448.5% |

## By Asset / TF / Pattern

| Asset | TF | Pattern | Side | Trades | Win | Exp | PF | DD |
|---|---|---|---|---|---|---|---|---|
| crypto | 1w | flat | long | 7 | 57.1% | 51.71% | 7.30 | -44.0% |
| stock | 1w | flat | long | 67 | 73.1% | 12.55% | 6.78 | -40.2% |
| stock | 1d | flat | long | 82 | 67.1% | 3.92% | 3.77 | -32.9% |
| stock | 4h | flat | long | 146 | 58.9% | 2.08% | 3.03 | -37.0% |
| stock | 1h | flat | long | 444 | 61.0% | 1.19% | 2.78 | -23.5% |
| crypto | 1d | flat | short | 27 | 66.7% | 4.43% | 1.94 | -69.3% |
| crypto | 4h | flat | short | 131 | 65.6% | 1.36% | 1.82 | -43.6% |
| crypto | 1d | flat | long | 26 | 53.8% | 7.05% | 1.81 | -71.3% |
| crypto | 4h | flat | long | 111 | 55.9% | 1.59% | 1.73 | -62.3% |
| crypto | 1h | flat | long | 226 | 51.3% | 0.33% | 1.34 | -25.8% |
| crypto | 1w | flat | short | 10 | 60.0% | 0.95% | 1.04 | -98.8% |
| stock | 4h | flat | short | 127 | 46.5% | 0.04% | 1.02 | -50.1% |
| stock | 1d | flat | short | 73 | 46.6% | -0.04% | 0.99 | -73.7% |
| stock | 1w | flat | short | 35 | 28.6% | -8.48% | 0.23 | -97.3% |

## Best Setup Keys

| Setup | Trades | Win | Exp | PF | DD |
|---|---|---|---|---|---|
| crypto|1w|flat|long|none|next_bar_open | 7 | 57.1% | 51.71% | 7.30 | -44.0% |
| stock|1w|flat|long|none|next_open | 67 | 73.1% | 12.55% | 6.78 | -40.2% |
| stock|1d|flat|long|none|next_open | 82 | 67.1% | 3.92% | 3.77 | -32.9% |
| stock|4h|flat|long|none|next_open | 146 | 58.9% | 2.08% | 3.03 | -37.0% |
| stock|1h|flat|long|none|next_open | 444 | 61.0% | 1.19% | 2.78 | -23.5% |
| crypto|1d|flat|short|none|next_bar_open | 27 | 66.7% | 4.43% | 1.94 | -69.3% |
| crypto|4h|flat|short|none|next_bar_open | 131 | 65.6% | 1.36% | 1.82 | -43.6% |
| crypto|1d|flat|long|none|next_bar_open | 26 | 53.8% | 7.05% | 1.81 | -71.3% |
| crypto|4h|flat|long|none|next_bar_open | 111 | 55.9% | 1.59% | 1.73 | -62.3% |
| crypto|1h|flat|long|none|next_bar_open | 226 | 51.3% | 0.33% | 1.34 | -25.8% |
| crypto|1w|flat|short|none|next_bar_open | 10 | 60.0% | 0.95% | 1.04 | -98.8% |
| stock|4h|flat|short|none|next_open | 127 | 46.5% | 0.04% | 1.02 | -50.1% |
| stock|1d|flat|short|none|next_open | 73 | 46.6% | -0.04% | 0.99 | -73.7% |
| stock|1w|flat|short|none|next_open | 35 | 28.6% | -8.48% | 0.23 | -97.3% |

## Walk Forward Folds

| Fold | Start | End | Trades | Win | Exp | PF | DD |
|---|---|---|---|---|---|---|---|
| 1 | 2017-01-16T00:00:00+00:00 | 2023-10-15T04:00:00+00:00 | 252 | 60.7% | 3.75% | 2.07 | -98.6% |
| 2 | 2023-10-16T00:00:00+00:00 | 2024-06-10T16:00:00+00:00 | 252 | 59.5% | 1.70% | 2.26 | -53.1% |
| 3 | 2024-06-11T16:00:00+00:00 | 2024-12-16T20:00:00+00:00 | 252 | 59.9% | 1.97% | 2.77 | -32.1% |
| 4 | 2024-12-16T20:30:00+00:00 | 2025-07-08T12:00:00+00:00 | 252 | 56.3% | 1.37% | 1.81 | -89.0% |
| 5 | 2025-07-08T14:00:00+00:00 | 2026-01-13T16:00:00+00:00 | 252 | 54.0% | 1.20% | 1.67 | -54.9% |
| 6 | 2026-01-13T16:00:00+00:00 | 2026-06-04T17:30:00+00:00 | 252 | 54.8% | 1.14% | 1.57 | -77.0% |

## How To Use

- Use this as the historical baseline before turning on a bot.
- Then run `forward_signal_logger.py add` for every alert and `settle` for every exit.
- Compare live forward trades with this baseline using `compare_backtest_forward.py`.
- Do not optimize against the forward log; it is the reality check.
