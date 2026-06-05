# Top Stocks Multi-TF Decision Test

Generated: `2026-06-05T10:01:02+00:00`

## Universe

NVDA, AAPL, GOOGL, MSFT, AMZN, AVGO, TSLA, META, JPM, BRK-B, LLY, V, MA, NFLX, XOM, WMT, COST, UNH, ORCL, HD

Universe rationale: current large-cap/liquid US stocks, aligned with current market-cap sources and repo research universe. Crypto/FX excluded because current probability calibration is stock-first.

## Method

- Data source: `yfinance`, adjusted OHLC.
- Timeframes: `15m`, `30m`, `1h`, `4h` (resampled from 1h), `1d`, `1w`.
- Entry: figure confirmation bar (`confirmation_idx`) only; no look-ahead entry at extremum.
- Exit: first of TP, SL, or time exit. TP/SL distance = figure amplitude. Flat fade uses 20 bars; Double Correction fade uses 50 bars; comparison rows use 20 bars for other cases.
- Costs: repo stock model `0.08%` per side, so `0.16%` round trip.
- Tested actions: `fade` and `follow`; MTF policies: no HTF, current Pine not-against-HTF, and old figure-with-HTF research policy.

## Best reliable pattern/timeframe/action rows

| fig_type | interval | mode | mtf_policy | n | win | mean | pf | sharpe_trade | tp_rate | sl_rate | avg_bars |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| flat | 4h | fade | none | 41 | 63.4% | 1.69% | 3.43 | 6.69 | 39.02% | 19.51% | 13.02 |
| impulse | 30m | fade | figure_with_htf | 32 | 68.8% | 1.37% | 4.17 | 7.10 | 3.12% | 0.00% | 19.75 |
| flat | 1h | fade | figure_with_htf | 110 | 55.5% | 0.55% | 1.87 | 3.64 | 35.45% | 26.36% | 13.07 |
| flat | 1h | fade | none | 182 | 55.5% | 0.50% | 1.63 | 2.76 | 29.67% | 23.63% | 14.36 |
| flat | 15m | fade | figure_with_htf | 32 | 56.2% | 0.16% | 1.89 | 3.78 | 37.50% | 28.12% | 10.91 |
| flat | 15m | fade | none | 53 | 58.5% | 0.16% | 1.53 | 2.37 | 26.42% | 22.64% | 13.42 |
| impulse | 1w | follow | none | 54 | 66.7% | 4.11% | 1.51 | 2.34 | 3.70% | 3.70% | 19.91 |
| flat | 1h | fade | trade_not_against_htf | 72 | 55.6% | 0.43% | 1.40 | 1.95 | 20.83% | 19.44% | 16.33 |
| impulse | 4h | follow | figure_with_htf | 34 | 55.9% | 0.41% | 1.22 | 1.21 | 2.94% | 0.00% | 19.74 |
| impulse | 4h | follow | trade_not_against_htf | 34 | 55.9% | 0.41% | 1.22 | 1.21 | 2.94% | 0.00% | 19.74 |

## MTF policy comparison for tradable patterns

| fig_type | mtf_policy | n | win | mean | pf | sharpe_trade | tp_rate | sl_rate | avg_bars |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| double_corr | trade_not_against_htf | 38 | 100.0% | 8.17% | n/a | 15.14 | 57.89% | 0.00% | 38.42 |
| double_corr | none | 52 | 98.1% | 9.08% | 67.59 | 11.69 | 51.92% | 0.00% | 39.44 |
| double_corr | figure_with_htf | 14 | 92.9% | 11.55% | 23.80 | 9.42 | 35.71% | 0.00% | 42.21 |
| flat | trade_not_against_htf | 154 | 63.0% | 1.21% | 1.95 | 3.05 | 22.08% | 16.23% | 16.14 |
| flat | none | 343 | 59.2% | 0.98% | 1.97 | 2.92 | 30.90% | 22.16% | 13.99 |
| flat | figure_with_htf | 189 | 56.1% | 0.79% | 2.01 | 2.87 | 38.10% | 26.98% | 12.23 |

## Portfolio variants

| variant | n | CAGR | Sharpe | Max DD | Calmar | Win | Final |
|---|---:|---:|---:|---:|---:|---:|---:|
| Flat+DC fade all TF / no HTF | 395 | 9.2% | 1.63 | -4.6% | 1.99 | 64.3% | $220,687 |
| Flat+DC fade all TF / Pine HTF not-against | 192 | 5.3% | 1.29 | -3.2% | 1.67 | 70.3% | $158,395 |
| Flat+DC fade all TF / old figure-with-HTF | 203 | 4.9% | 1.12 | -4.4% | 1.12 | 58.6% | $139,525 |
| Flat+DC fade 1h+4h+1d / no HTF | 286 | 12.4% | 1.84 | -4.6% | 2.67 | 63.3% | $174,792 |
| DoubleCorr fade 1h+4h / no HTF | 32 | 8.6% | 2.51 | -0.3% | 25.43 | 96.9% | $124,873 |
| Flat fade 1h+1d / no HTF | 207 | 4.2% | 0.78 | -11.2% | 0.38 | 57.0% | $121,841 |

## BUY vs SELL side calibration candidates

| fig_type | interval | side | n | win | mean | pf | sharpe_trade | tp_rate | sl_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| double_corr | 1h | long | 15 | 100.0% | 5.91% | n/a | 18.84 | 33.33% | 0.00% |
| double_corr | 1h | short | 10 | 100.0% | 6.13% | n/a | 20.18 | 80.00% | 0.00% |
| flat | 15m | long | 27 | 59.3% | 0.01% | 1.02 | 0.11 | 25.93% | 33.33% |
| flat | 15m | short | 26 | 57.7% | 0.32% | 2.51 | 5.02 | 26.92% | 11.54% |
| flat | 1d | long | 16 | 75.0% | 5.09% | 4.20 | 8.75 | 37.50% | 12.50% |
| flat | 1h | long | 90 | 66.7% | 1.24% | 3.27 | 6.34 | 38.89% | 17.78% |
| flat | 1h | short | 92 | 44.6% | -0.23% | 0.78 | -1.49 | 20.65% | 29.35% |
| flat | 1w | long | 13 | 69.2% | 9.09% | 4.40 | 8.65 | 53.85% | 23.08% |
| flat | 30m | long | 11 | 63.6% | 0.77% | 2.97 | 7.29 | 27.27% | 9.09% |
| flat | 30m | short | 16 | 75.0% | 1.39% | 3.94 | 8.91 | 25.00% | 12.50% |
| flat | 4h | long | 20 | 65.0% | 2.03% | 4.52 | 7.31 | 35.00% | 20.00% |
| flat | 4h | short | 21 | 61.9% | 1.37% | 2.68 | 5.90 | 42.86% | 19.05% |

## Evidence that impulse/triangle should stay no-trade context

| fig_type | interval | mode | mtf_policy | n | win | mean | pf | sharpe_trade |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| impulse | 30m | fade | none | 79 | 49.4% | 0.21% | 1.23 | 1.18 |
| triangle | 1d | fade | none | 243 | 46.5% | 0.39% | 1.14 | 0.71 |
| triangle | 1h | fade | none | 1177 | 48.5% | 0.08% | 1.10 | 0.55 |
| triangle | 4h | fade | none | 367 | 50.4% | 0.12% | 1.08 | 0.43 |
| impulse | 4h | fade | none | 146 | 46.6% | 0.12% | 1.06 | 0.33 |
| triangle | 1w | fade | none | 98 | 54.1% | -0.27% | 0.96 | -0.28 |
| impulse | 1d | fade | none | 98 | 46.9% | -0.46% | 0.89 | -0.71 |
| triangle | 30m | fade | none | 172 | 44.8% | -0.09% | 0.87 | -0.84 |
| impulse | 1h | fade | none | 566 | 45.9% | -0.21% | 0.83 | -0.99 |
| impulse | 15m | fade | none | 175 | 42.3% | -0.19% | 0.75 | -1.75 |
| triangle | 15m | fade | none | 336 | 45.5% | -0.11% | 0.76 | -1.56 |
| impulse | 1w | fade | none | 54 | 33.3% | -4.43% | 0.64 | -2.53 |

## Best ticker slices (diagnostic, not enough alone)

| ticker | fig_type | interval | n | win | mean | pf | sharpe_trade |
| --- | --- | --- | --- | --- | --- | --- | --- |
| NVDA | flat | 1h | 6 | 100.0% | 3.47% | n/a | 21.86 |
| BRK-B | flat | 1h | 8 | 75.0% | 0.99% | 23.63 | 17.26 |
| TSLA | flat | 1h | 6 | 83.3% | 3.93% | 5.69 | 10.82 |
| WMT | flat | 1h | 9 | 77.8% | 1.03% | 4.18 | 9.40 |
| AVGO | flat | 1h | 5 | 60.0% | 2.54% | 5.00 | 7.53 |
| UNH | flat | 1h | 10 | 60.0% | 0.68% | 2.44 | 4.75 |
| GOOGL | flat | 1h | 13 | 69.2% | 0.85% | 1.97 | 4.65 |
| XOM | flat | 1h | 10 | 70.0% | 0.63% | 2.60 | 4.57 |
| MA | flat | 1h | 9 | 55.6% | 0.08% | 1.21 | 1.22 |
| V | flat | 15m | 8 | 75.0% | 0.04% | 1.20 | 0.99 |

## Skipped downloads / data issues

_none_

## Decision notes

- Do not treat high win-rate rows with tiny `n` as final. Prefer rows with `n >= 30`, positive mean net, PF > 1.2, and stable portfolio behavior.
- For Anton, the indicator should show `BUY/SELL` only for fresh Flat/Double Correction fade setups with valid remaining R:R. Impulse/Triangle remain context/no-trade unless future tests prove otherwise.
- Current Pine HTF filter must be reviewed against this report: if `trade_not_against_htf` underperforms `none`, it should become optional or default-off for Flat/DC fade.
