# Probability Overlay v0 Historical Grid

Generated: `2026-06-06T08:59:03.652842+00:00`

Scope: stocks only. This mirrors the simplified `EWB — Probability Overlay v0` pivot-window detector, not the full Monowaves MTF runtime.

## Run scope

- Data provider: `tiingo`.
- Requested universe modes: top20/top100; executed max rank: `100`.
- Tickers with usable data: `54` / `100`.
- Base simulated rows after variants: `1352055`.
- Timeframes: `15m, 30m, 1h, 4h, 1d, 1w`.
- Pivot settings: left=5, right=5, min amplitude=0.5 ATR.

## Requested comparison slices

| Universe | Slice | Trades | Win | EV | CAGR | Sharpe | DD | Final |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| top20 | Flat+DC all TF / no HTF | 5196 | 47.4% | -0.3% | -95.3% | -3.08 | -100.0% | $0 |
| top20 | Flat+DC all TF / Pine HTF | 3124 | 46.8% | -0.4% | -92.7% | -2.88 | -100.0% | $0 |
| top20 | DoubleCorr 1h+4h / no HTF | 380 | 46.6% | -0.2% | -50.5% | -0.58 | -96.2% | $24,991 |
| top20 | Flat baseline | 3656 | 47.2% | -0.1% | -64.3% | -2.03 | -100.0% | $10 |
| top20 | Flat 1h long | 410 | 49.0% | -0.1% | -24.8% | -0.76 | -63.5% | $56,970 |
| top20 | Flat 1h short | 381 | 43.8% | -0.3% | -48.8% | -2.06 | -81.8% | $26,606 |
| top20 | Impulse/Triangle research | 120 | 38.3% | -0.4% | -7.5% | -1.58 | -47.5% | $59,133 |
| top100 | Flat+DC all TF / no HTF | 7033 | 47.4% | -0.2% | -96.7% | -3.48 | -100.0% | $0 |
| top100 | Flat+DC all TF / Pine HTF | 4166 | 47.5% | -0.3% | -93.8% | -3.03 | -100.0% | $0 |
| top100 | DoubleCorr 1h+4h / no HTF | 380 | 46.6% | -0.2% | -50.5% | -0.58 | -96.2% | $24,991 |
| top100 | Flat baseline | 4945 | 46.9% | -0.2% | -73.4% | -2.80 | -100.0% | $1 |
| top100 | Flat 1h long | 410 | 49.0% | -0.1% | -24.8% | -0.76 | -63.5% | $56,970 |
| top100 | Flat 1h short | 381 | 43.8% | -0.3% | -48.8% | -2.06 | -81.8% | $26,606 |
| top100 | Impulse/Triangle research | 180 | 41.7% | -0.3% | -9.4% | -1.74 | -60.9% | $51,358 |

## MTF breakdown for Flat/DC default contract

| Universe | TF | MTF | Trades | Win | EV | DD | PF | TP | SL |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| top20 | 15m | none | 2199 | 46.0% | -0.2% | -98.5% | 0.77 | 25.0% | 24.4% |
| top20 | 15m | pine_htf_not_against | 1315 | 46.0% | -0.2% | -94.6% | 0.78 | 19.3% | 18.6% |
| top20 | 15m | warn | 2199 | 46.0% | -0.2% | -98.5% | 0.77 | 25.0% | 24.4% |
| top20 | 1d | none | 369 | 47.4% | -0.9% | -99.7% | 0.79 | 24.1% | 24.9% |
| top20 | 1d | pine_htf_not_against | 233 | 42.1% | -1.5% | -99.6% | 0.70 | 14.2% | 21.0% |
| top20 | 1d | warn | 369 | 47.4% | -0.9% | -99.7% | 0.79 | 24.1% | 24.9% |
| top20 | 1h | none | 1069 | 46.7% | -0.1% | -92.1% | 0.93 | 25.6% | 29.6% |
| top20 | 1h | pine_htf_not_against | 623 | 47.4% | 0.1% | -74.1% | 1.08 | 20.4% | 21.7% |
| top20 | 1h | warn | 1069 | 46.7% | -0.1% | -92.1% | 0.93 | 25.6% | 29.6% |
| top20 | 1w | none | 146 | 44.5% | -3.6% | -100.0% | 0.71 | 28.1% | 30.8% |
| top20 | 1w | pine_htf_not_against | 97 | 44.3% | -5.6% | -100.0% | 0.64 | 21.6% | 26.8% |
| top20 | 1w | warn | 146 | 44.5% | -3.6% | -100.0% | 0.71 | 28.1% | 30.8% |
| top20 | 30m | none | 1038 | 49.8% | -0.0% | -63.4% | 0.95 | 24.9% | 22.6% |
| top20 | 30m | pine_htf_not_against | 629 | 49.8% | -0.0% | -56.6% | 0.99 | 21.9% | 18.9% |
| top20 | 30m | warn | 1038 | 49.8% | -0.0% | -63.4% | 0.95 | 24.9% | 22.6% |
| top20 | 4h | none | 375 | 51.7% | -0.1% | -84.7% | 0.96 | 26.4% | 23.5% |
| top20 | 4h | pine_htf_not_against | 227 | 48.0% | -0.5% | -90.8% | 0.80 | 17.2% | 21.6% |
| top20 | 4h | warn | 375 | 51.7% | -0.1% | -84.7% | 0.96 | 26.4% | 23.5% |
| top100 | 15m | none | 2199 | 46.0% | -0.2% | -98.5% | 0.77 | 25.0% | 24.4% |
| top100 | 15m | pine_htf_not_against | 1315 | 46.0% | -0.2% | -94.6% | 0.78 | 19.3% | 18.6% |
| top100 | 15m | warn | 2199 | 46.0% | -0.2% | -98.5% | 0.77 | 25.0% | 24.4% |
| top100 | 1d | none | 369 | 47.4% | -0.9% | -99.7% | 0.79 | 24.1% | 24.9% |
| top100 | 1d | pine_htf_not_against | 233 | 42.1% | -1.5% | -99.6% | 0.70 | 14.2% | 21.0% |
| top100 | 1d | warn | 369 | 47.4% | -0.9% | -99.7% | 0.79 | 24.1% | 24.9% |
| top100 | 1h | none | 1069 | 46.7% | -0.1% | -92.1% | 0.93 | 25.6% | 29.6% |
| top100 | 1h | pine_htf_not_against | 623 | 47.4% | 0.1% | -74.1% | 1.08 | 20.4% | 21.7% |
| top100 | 1h | warn | 1069 | 46.7% | -0.1% | -92.1% | 0.93 | 25.6% | 29.6% |
| top100 | 1w | none | 146 | 44.5% | -3.6% | -100.0% | 0.71 | 28.1% | 30.8% |
| top100 | 1w | pine_htf_not_against | 97 | 44.3% | -5.6% | -100.0% | 0.64 | 21.6% | 26.8% |
| top100 | 1w | warn | 146 | 44.5% | -3.6% | -100.0% | 0.71 | 28.1% | 30.8% |
| top100 | 30m | none | 2875 | 48.4% | -0.1% | -98.5% | 0.90 | 23.9% | 24.8% |
| top100 | 30m | pine_htf_not_against | 1671 | 49.5% | -0.1% | -89.0% | 0.94 | 21.5% | 20.3% |
| top100 | 30m | warn | 2875 | 48.4% | -0.1% | -98.5% | 0.90 | 23.9% | 24.8% |
| top100 | 4h | none | 375 | 51.7% | -0.1% | -84.7% | 0.96 | 26.4% | 23.5% |
| top100 | 4h | pine_htf_not_against | 227 | 48.0% | -0.5% | -90.8% | 0.80 | 17.2% | 21.6% |
| top100 | 4h | warn | 375 | 51.7% | -0.1% | -84.7% | 0.96 | 26.4% | 23.5% |

## Best winrate setups

| Universe | TF | Pattern | Side | MTF | Entry | Late | TP | SL | Exit | Trades | Win | EV | Test win | Test EV | DD | PF | Conf |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| top20 | 1w | flat | long | pine_htf_not_against | confirm_close | off | 0.500 | 1.250 | full | 28 | 89.3% | 7.5% | 100.0% | 12.8% | -9.6% | 9.29 | low |
| top20 | 1w | flat | long | pine_htf_not_against | next_open | 35% | 0.500 | 1.250 | full | 28 | 89.3% | 7.7% | 100.0% | 13.3% | -14.2% | 7.78 | low |
| top20 | 1w | flat | long | pine_htf_not_against | next_open | 35% | 0.618 | 1.250 | full | 28 | 89.3% | 9.2% | 100.0% | 14.9% | -14.2% | 9.17 | low |
| top20 | 1w | flat | long | pine_htf_not_against | next_open | 35% | 1.000 | 1.250 | full | 28 | 89.3% | 12.5% | 100.0% | 18.5% | -14.2% | 12.03 | low |
| top20 | 1w | flat | long | pine_htf_not_against | next_open | 35% | 1.618 | 1.250 | partial_50_100_1618 | 28 | 89.3% | 11.4% | 100.0% | 16.6% | -14.2% | 11.10 | low |
| top20 | 1w | flat | long | pine_htf_not_against | next_open | 50% | 0.500 | 1.250 | full | 28 | 89.3% | 7.7% | 100.0% | 13.3% | -14.2% | 7.78 | low |
| top20 | 1w | flat | long | pine_htf_not_against | next_open | 50% | 0.618 | 1.250 | full | 28 | 89.3% | 9.2% | 100.0% | 14.9% | -14.2% | 9.17 | low |
| top20 | 1w | flat | long | pine_htf_not_against | next_open | 50% | 1.000 | 1.250 | full | 28 | 89.3% | 12.5% | 100.0% | 18.5% | -14.2% | 12.03 | low |
| top20 | 1w | flat | long | pine_htf_not_against | next_open | 50% | 1.618 | 1.250 | partial_50_100_1618 | 28 | 89.3% | 11.4% | 100.0% | 16.6% | -14.2% | 11.10 | low |
| top20 | 1w | flat | long | pine_htf_not_against | next_open | off | 0.500 | 1.250 | full | 28 | 89.3% | 7.7% | 100.0% | 13.3% | -14.2% | 7.78 | low |
| top20 | 1w | flat | long | pine_htf_not_against | next_open | off | 0.618 | 1.250 | full | 28 | 89.3% | 9.2% | 100.0% | 14.9% | -14.2% | 9.17 | low |
| top20 | 1w | flat | long | pine_htf_not_against | next_open | off | 1.000 | 1.250 | full | 28 | 89.3% | 12.5% | 100.0% | 18.5% | -14.2% | 12.03 | low |
| top20 | 1w | flat | long | pine_htf_not_against | next_open | off | 1.618 | 1.250 | partial_50_100_1618 | 28 | 89.3% | 11.4% | 100.0% | 16.6% | -14.2% | 11.10 | low |
| top100 | 1w | flat | long | pine_htf_not_against | confirm_close | off | 0.500 | 1.250 | full | 28 | 89.3% | 7.5% | 100.0% | 12.8% | -9.6% | 9.29 | low |
| top100 | 1w | flat | long | pine_htf_not_against | next_open | 35% | 0.500 | 1.250 | full | 28 | 89.3% | 7.7% | 100.0% | 13.3% | -14.2% | 7.78 | low |

## Best balanced setups

| Universe | TF | Pattern | Side | MTF | Entry | Late | TP | SL | Exit | Trades | Win | EV | Test win | Test EV | DD | PF | Conf |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| top20 | 1w | flat | long | pine_htf_not_against | next_open | 50% | 1.618 | 1.250 | full | 28 | 82.1% | 14.1% | 100.0% | 17.9% | -15.0% | 8.80 | low |
| top20 | 1w | flat | long | pine_htf_not_against | next_open | 35% | 1.618 | 1.250 | full | 28 | 82.1% | 14.1% | 100.0% | 17.9% | -15.0% | 8.80 | low |
| top100 | 1w | flat | long | pine_htf_not_against | next_open | off | 1.618 | 1.250 | full | 28 | 82.1% | 14.1% | 100.0% | 17.9% | -15.0% | 8.80 | low |
| top20 | 1w | flat | long | pine_htf_not_against | next_open | off | 1.618 | 1.250 | full | 28 | 82.1% | 14.1% | 100.0% | 17.9% | -15.0% | 8.80 | low |
| top100 | 1w | flat | long | pine_htf_not_against | next_open | 50% | 1.618 | 1.250 | full | 28 | 82.1% | 14.1% | 100.0% | 17.9% | -15.0% | 8.80 | low |
| top100 | 1w | flat | long | pine_htf_not_against | next_open | 35% | 1.618 | 1.250 | full | 28 | 82.1% | 14.1% | 100.0% | 17.9% | -15.0% | 8.80 | low |
| top100 | 1w | flat | long | pine_htf_not_against | next_open | 20% | 1.618 | 1.250 | full | 27 | 81.5% | 14.0% | 100.0% | 17.9% | -15.0% | 8.44 | low |
| top20 | 1w | flat | long | pine_htf_not_against | next_open | 20% | 1.618 | 1.250 | full | 27 | 81.5% | 14.0% | 100.0% | 17.9% | -15.0% | 8.44 | low |
| top100 | 1w | flat | long | pine_htf_not_against | next_open | 50% | 1.618 | 1.000 | full | 28 | 78.6% | 13.4% | 100.0% | 17.9% | -12.6% | 7.28 | low |
| top20 | 1w | flat | long | pine_htf_not_against | next_open | 35% | 1.618 | 1.000 | full | 28 | 78.6% | 13.4% | 100.0% | 17.9% | -12.6% | 7.28 | low |
| top100 | 1w | flat | long | pine_htf_not_against | next_open | off | 1.618 | 1.000 | full | 28 | 78.6% | 13.4% | 100.0% | 17.9% | -12.6% | 7.28 | low |
| top100 | 1w | flat | long | pine_htf_not_against | next_open | 35% | 1.618 | 1.000 | full | 28 | 78.6% | 13.4% | 100.0% | 17.9% | -12.6% | 7.28 | low |
| top20 | 1w | flat | long | pine_htf_not_against | next_open | 50% | 1.618 | 1.000 | full | 28 | 78.6% | 13.4% | 100.0% | 17.9% | -12.6% | 7.28 | low |
| top20 | 1w | flat | long | pine_htf_not_against | next_open | off | 1.618 | 1.000 | full | 28 | 78.6% | 13.4% | 100.0% | 17.9% | -12.6% | 7.28 | low |
| top20 | 1w | flat | long | pine_htf_not_against | next_open | 20% | 1.618 | 1.000 | full | 27 | 77.8% | 13.2% | 100.0% | 17.9% | -12.6% | 6.98 | low |

## Setups to disable or keep as WAIT/research

| Universe | TF | Pattern | Side | MTF | Entry | Late | TP | SL | Exit | Trades | Win | EV | Test win | Test EV | DD | PF | Conf |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| top20 | 1w | double_corr | short | pine_htf_not_against | next_open | 20% | 1.618 | 1.000 | full | 34 | 23.5% | -25.3% | 14.3% | -17.5% | -100.0% | 0.18 | low |
| top20 | 1w | double_corr | short | pine_htf_not_against | next_open | 35% | 1.618 | 1.000 | full | 34 | 23.5% | -25.3% | 14.3% | -17.5% | -100.0% | 0.18 | low |
| top20 | 1w | double_corr | short | pine_htf_not_against | next_open | 50% | 1.618 | 1.000 | full | 34 | 23.5% | -25.3% | 14.3% | -17.5% | -100.0% | 0.18 | low |
| top20 | 1w | double_corr | short | pine_htf_not_against | next_open | off | 1.618 | 1.000 | full | 34 | 23.5% | -25.3% | 14.3% | -17.5% | -100.0% | 0.18 | low |
| top100 | 1w | double_corr | short | pine_htf_not_against | next_open | 20% | 1.618 | 1.000 | full | 34 | 23.5% | -25.3% | 14.3% | -17.5% | -100.0% | 0.18 | low |
| top100 | 1w | double_corr | short | pine_htf_not_against | next_open | 35% | 1.618 | 1.000 | full | 34 | 23.5% | -25.3% | 14.3% | -17.5% | -100.0% | 0.18 | low |
| top100 | 1w | double_corr | short | pine_htf_not_against | next_open | 50% | 1.618 | 1.000 | full | 34 | 23.5% | -25.3% | 14.3% | -17.5% | -100.0% | 0.18 | low |
| top100 | 1w | double_corr | short | pine_htf_not_against | next_open | off | 1.618 | 1.000 | full | 34 | 23.5% | -25.3% | 14.3% | -17.5% | -100.0% | 0.18 | low |
| top20 | 1w | double_corr | short | pine_htf_not_against | next_open | 20% | 1.618 | 1.250 | full | 34 | 26.5% | -25.1% | 14.3% | -15.6% | -106.0% | 0.21 | low |
| top20 | 1w | double_corr | short | pine_htf_not_against | next_open | 35% | 1.618 | 1.250 | full | 34 | 26.5% | -25.1% | 14.3% | -15.6% | -106.0% | 0.21 | low |
| top20 | 1w | double_corr | short | pine_htf_not_against | next_open | 50% | 1.618 | 1.250 | full | 34 | 26.5% | -25.1% | 14.3% | -15.6% | -106.0% | 0.21 | low |
| top20 | 1w | double_corr | short | pine_htf_not_against | next_open | off | 1.618 | 1.250 | full | 34 | 26.5% | -25.1% | 14.3% | -15.6% | -106.0% | 0.21 | low |

## Impulse/Triangle research check

| Universe | TF | Pattern | Side | MTF | Entry | Late | TP | SL | Exit | Trades | Win | EV | Test win | Test EV | DD | PF | Conf |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| top100 | 30m | triangle | short | none | confirm_close | off | 1.000 | 1.000 | full | 79 | 50.6% | -0.3% | 68.8% | 0.5% | -25.5% | 0.67 | low |
| top20 | 30m | triangle | short | none | confirm_close | off | 1.000 | 1.000 | full | 33 | 48.5% | -0.5% | 57.1% | -1.0% | -18.3% | 0.50 | low |
| top20 | 15m | triangle | short | none | confirm_close | off | 1.000 | 1.000 | full | 39 | 30.8% | -0.3% | 37.5% | -0.2% | -10.0% | 0.45 | low |
| top100 | 15m | triangle | short | none | confirm_close | off | 1.000 | 1.000 | full | 39 | 30.8% | -0.3% | 37.5% | -0.2% | -10.0% | 0.45 | low |

## Probability filter observations

| Universe | Min P | Min N | No low | Trades | Win | EV | DD | PF |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| top100 | 58 | 0 | False | 6450 | 48.5% | -0.4% | -100.0% | 0.83 |
| top100 | 60 | 0 | False | 6450 | 48.5% | -0.4% | -100.0% | 0.83 |
| top100 | 65 | 0 | False | 6450 | 48.5% | -0.4% | -100.0% | 0.83 |
| top20 | 58 | 0 | False | 4997 | 47.7% | -0.5% | -100.0% | 0.80 |
| top20 | 60 | 0 | False | 4997 | 47.7% | -0.5% | -100.0% | 0.80 |
| top20 | 65 | 0 | False | 4997 | 47.7% | -0.5% | -100.0% | 0.80 |
| top100 | 55 | 0 | False | 17239 | 47.6% | -0.3% | -100.0% | 0.84 |
| top20 | 55 | 0 | False | 12523 | 47.5% | -0.3% | -100.0% | 0.82 |
| top100 | 50 | 0 | False | 18232 | 47.4% | -0.3% | -100.0% | 0.83 |
| top100 | 52 | 0 | False | 18232 | 47.4% | -0.3% | -100.0% | 0.83 |
| top20 | 55 | 0 | True | 7526 | 47.4% | -0.1% | -100.0% | 0.87 |
| top20 | 55 | 30 | False | 7526 | 47.4% | -0.1% | -100.0% | 0.87 |

## Notes

- `Pine HTF` here is an external Python HTF filter applied to overlay signals; the overlay itself does not draw MTF monowaves.
- Use this report to compare overlay detector quality with `historical_signal_grid_report.md`; do not merge the two signal sources blindly.
- Rows with very high winrate and small sample still need out-of-sample/manual parity before becoming TradingView defaults.

## Files

- Trades: `/Users/DEV/Elliott-wave/python/data/probability_overlay_historical_grid_trades.parquet`
- JSON summary: `/Users/DEV/Elliott-wave/brain-output/signals/probability_overlay_historical_grid_summary.json`
