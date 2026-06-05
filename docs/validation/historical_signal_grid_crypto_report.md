# Historical Signal Grid - Elliott Wave Brain

Generated: `2026-06-05T14:57:13.970043+00:00`

Scope: crypto only. Stocks, ETFs, FX and futures are excluded. Entry is evaluated on the figure confirmation bar or later; `next_bar_open` means the next 24/7 crypto bar open.

## Run scope

- Asset class: `crypto`.
- Requested universe modes: top20/top50/top100; executed max rank: `20`.
- Tickers with usable data: `20` / `20`.
- Base simulated rows after variants: `224904`.
- Timeframes: `15m, 30m, 1h, 4h, 1d, 1w`.
- Calibration source: `/Users/DEV/Elliott-wave/brain-output/indicator-spec/probability_calibration_crypto_v0.json`. If the crypto calibration file is missing, probability filters are disabled and the run is treated as uncalibrated research.

## Best winrate setups

| Universe | TF | Pattern | Side | MTF | Entry | Late | TP | SL | Exit | Trades | Win | EV | Test win | Test EV | DD | PF | Conf |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| top20 | 15m | double_corr | short | none | next_bar_open | off | 0.500 | 0.750 | full | 32 | 93.8% | 1.65% | 71.4% | 0.92% | -0.5% | 83.75 | medium |
| top20 | 15m | double_corr | short | none | next_bar_open | off | 0.500 | 1.000 | full | 32 | 93.8% | 1.65% | 71.4% | 0.92% | -0.5% | 83.75 | medium |
| top20 | 15m | double_corr | short | none | next_bar_open | off | 0.500 | 1.250 | full | 32 | 93.8% | 1.65% | 71.4% | 0.92% | -0.5% | 83.75 | medium |
| top20 | 15m | double_corr | short | warn | next_bar_open | off | 0.500 | 0.750 | full | 32 | 93.8% | 1.65% | 71.4% | 0.92% | -0.5% | 83.75 | medium |
| top20 | 15m | double_corr | short | warn | next_bar_open | off | 0.500 | 1.000 | full | 32 | 93.8% | 1.65% | 71.4% | 0.92% | -0.5% | 83.75 | medium |
| top20 | 15m | double_corr | short | warn | next_bar_open | off | 0.500 | 1.250 | full | 32 | 93.8% | 1.65% | 71.4% | 0.92% | -0.5% | 83.75 | medium |
| top20 | 15m | double_corr | short | none | confirm_close | off | 0.500 | 0.750 | full | 32 | 90.6% | 1.62% | 71.4% | 0.90% | -0.5% | 49.74 | medium |
| top20 | 15m | double_corr | short | none | confirm_close | off | 0.500 | 1.000 | full | 32 | 90.6% | 1.62% | 71.4% | 0.90% | -0.5% | 49.74 | medium |
| top20 | 15m | double_corr | short | none | confirm_close | off | 0.500 | 1.250 | full | 32 | 90.6% | 1.62% | 71.4% | 0.90% | -0.5% | 49.74 | medium |
| top20 | 15m | double_corr | short | none | next_bar_open | off | 0.618 | 0.750 | full | 32 | 90.6% | 1.80% | 71.4% | 1.21% | -1.4% | 37.13 | medium |
| top20 | 15m | double_corr | short | none | next_bar_open | off | 0.618 | 1.000 | full | 32 | 90.6% | 1.80% | 71.4% | 1.21% | -1.4% | 37.13 | medium |
| top20 | 15m | double_corr | short | none | next_bar_open | off | 0.618 | 1.250 | full | 32 | 90.6% | 1.80% | 71.4% | 1.21% | -1.4% | 37.13 | medium |

## Best balanced setups

| Universe | TF | Pattern | Side | MTF | Entry | Late | TP | SL | Exit | Trades | Win | EV | Test win | Test EV | DD | PF | Conf |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| top20 | 4h | flat | long | block_against_htf | confirm_close | off | 1.000 | 0.750 | full | 54 | 57.4% | 3.35% | 45.5% | 0.17% | -19.6% | 2.82 | high |
| top20 | 4h | flat | long | fade_not_against_htf | confirm_close | off | 1.000 | 0.750 | full | 54 | 57.4% | 3.35% | 45.5% | 0.17% | -19.6% | 2.82 | high |
| top20 | 4h | flat | long | long_only_htf_up_short_only_htf_down | confirm_close | off | 1.000 | 0.750 | full | 54 | 57.4% | 3.35% | 45.5% | 0.17% | -19.6% | 2.82 | high |
| top20 | 4h | flat | long | block_against_htf | confirm_close | off | 0.618 | 0.750 | full | 54 | 61.1% | 1.97% | 54.5% | 0.02% | -17.6% | 2.15 | high |
| top20 | 4h | flat | long | fade_not_against_htf | confirm_close | off | 0.618 | 0.750 | full | 54 | 61.1% | 1.97% | 54.5% | 0.02% | -17.6% | 2.15 | high |
| top20 | 4h | flat | long | long_only_htf_up_short_only_htf_down | confirm_close | off | 0.618 | 0.750 | full | 54 | 61.1% | 1.97% | 54.5% | 0.02% | -17.6% | 2.15 | high |
| top20 | 30m | flat | short | block_against_htf | confirm_close | off | 1.618 | 0.750 | full | 134 | 56.0% | 0.77% | 44.4% | 0.08% | -11.9% | 2.38 | high |
| top20 | 30m | flat | short | fade_not_against_htf | confirm_close | off | 1.618 | 0.750 | full | 134 | 56.0% | 0.77% | 44.4% | 0.08% | -11.9% | 2.38 | high |
| top20 | 30m | flat | short | long_only_htf_up_short_only_htf_down | confirm_close | off | 1.618 | 0.750 | full | 133 | 55.6% | 0.78% | 44.4% | 0.08% | -11.9% | 2.38 | high |
| top20 | 30m | flat | short | block_against_htf | next_bar_open | off | 1.618 | 0.750 | full | 134 | 51.5% | 0.78% | 44.4% | 0.17% | -12.4% | 2.32 | high |
| top20 | 30m | flat | short | fade_not_against_htf | next_bar_open | off | 1.618 | 0.750 | full | 134 | 51.5% | 0.78% | 44.4% | 0.17% | -12.4% | 2.32 | high |
| top20 | 30m | flat | short | long_only_htf_up_short_only_htf_down | next_bar_open | off | 1.618 | 0.750 | full | 133 | 51.1% | 0.79% | 44.4% | 0.17% | -12.4% | 2.31 | high |

## Setups to disable or keep as WAIT/research

| Universe | TF | Pattern | Side | MTF | Entry | Late | TP | SL | Exit | Trades | Win | EV | Test win | Test EV | DD | PF | Conf |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| top20 | 15m | flat | short | long_only_htf_up_short_only_htf_down | confirm_close | off | 0.500 | 1.250 | full | 116 | 56.0% | -0.14% | 75.0% | 0.45% | -25.5% | 0.76 | low |
| top20 | 15m | flat | short | none | next_bar_open | off | 0.500 | 1.250 | full | 246 | 57.3% | -0.14% | 68.0% | 0.17% | -38.5% | 0.72 | low |
| top20 | 15m | flat | short | warn | next_bar_open | off | 0.500 | 1.250 | full | 246 | 57.3% | -0.14% | 68.0% | 0.17% | -38.5% | 0.72 | low |
| top20 | 15m | flat | short | block_against_htf | confirm_close | off | 0.500 | 1.250 | full | 118 | 56.8% | -0.13% | 75.0% | 0.45% | -24.9% | 0.78 | low |
| top20 | 15m | flat | short | fade_not_against_htf | confirm_close | off | 0.500 | 1.250 | full | 118 | 56.8% | -0.13% | 75.0% | 0.45% | -24.9% | 0.78 | low |
| top20 | 15m | flat | short | long_only_htf_up_short_only_htf_down | next_bar_open | off | 0.500 | 1.250 | full | 115 | 56.5% | -0.13% | 78.3% | 0.53% | -25.2% | 0.78 | low |
| top20 | 15m | flat | long | none | next_bar_open | off | 0.500 | 1.250 | full | 202 | 53.5% | -0.12% | 61.0% | 0.12% | -27.1% | 0.73 | low |
| top20 | 15m | flat | long | warn | next_bar_open | off | 0.500 | 1.250 | full | 202 | 53.5% | -0.12% | 61.0% | 0.12% | -27.1% | 0.73 | low |
| top20 | 15m | flat | long | block_against_htf | next_bar_open | off | 0.500 | 1.250 | full | 101 | 50.5% | -0.12% | 66.7% | 0.21% | -15.5% | 0.76 | low |
| top20 | 15m | flat | long | fade_not_against_htf | next_bar_open | off | 0.500 | 1.250 | full | 101 | 50.5% | -0.12% | 66.7% | 0.21% | -15.5% | 0.76 | low |
| top20 | 15m | flat | short | none | confirm_close | off | 0.500 | 1.250 | full | 248 | 58.5% | -0.11% | 68.0% | 0.16% | -35.1% | 0.75 | low |
| top20 | 15m | flat | short | warn | confirm_close | off | 0.500 | 1.250 | full | 248 | 58.5% | -0.11% | 68.0% | 0.16% | -35.1% | 0.75 | low |

## Research only: impulse/triangle check

| Universe | TF | Pattern | Side | MTF | Entry | Late | TP | SL | Exit | Trades | Win | EV | Test win | Test EV | DD | PF | Conf |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| top20 | 1w | impulse | long | none | confirm_close | off | 1.000 | 1.000 | full | 31 | 71.0% | 54.65% | 28.6% | 4.90% | -86.2% | 5.98 | low |
| top20 | 1w | triangle | long | none | confirm_close | off | 1.000 | 1.000 | full | 48 | 43.8% | 6.48% | 20.0% | -30.04% | -99.6% | 1.40 | low |
| top20 | 1d | triangle | short | none | confirm_close | off | 1.000 | 1.000 | full | 182 | 63.2% | 1.88% | 75.7% | 10.24% | -99.4% | 1.29 | low |
| top20 | 4h | impulse | long | none | confirm_close | off | 1.000 | 1.000 | full | 362 | 47.0% | 1.16% | 32.9% | -3.69% | -93.4% | 1.24 | low |
| top20 | 1d | impulse | long | none | confirm_close | off | 1.000 | 1.000 | full | 74 | 44.6% | 0.63% | 20.0% | -17.82% | -99.6% | 1.05 | low |
| top20 | 4h | triangle | short | none | confirm_close | off | 1.000 | 1.000 | full | 1008 | 50.8% | 0.17% | 52.0% | 0.35% | -94.8% | 1.06 | low |
| top20 | 1d | triangle | long | none | confirm_close | off | 1.000 | 1.000 | full | 190 | 42.6% | 0.28% | 28.9% | -3.73% | -96.4% | 1.04 | low |
| top20 | 15m | impulse | short | none | confirm_close | off | 1.000 | 1.000 | full | 752 | 45.7% | -0.19% | 49.0% | -0.06% | -85.3% | 0.83 | low |
| top20 | 1h | triangle | short | none | confirm_close | off | 1.000 | 1.000 | full | 1892 | 47.7% | -0.10% | 47.8% | -0.04% | -96.2% | 0.93 | low |
| top20 | 30m | impulse | long | none | confirm_close | off | 1.000 | 1.000 | full | 642 | 42.5% | -0.23% | 37.2% | -0.68% | -89.9% | 0.87 | low |
| top20 | 4h | triangle | long | none | confirm_close | off | 1.000 | 1.000 | full | 1031 | 44.6% | -0.05% | 41.1% | -0.62% | -98.4% | 0.98 | low |
| top20 | 30m | triangle | short | none | confirm_close | off | 1.000 | 1.000 | full | 1943 | 45.0% | -0.16% | 49.6% | 0.01% | -98.0% | 0.84 | low |

## Probability filter observations

| Universe | TF | Pattern | Side | MTF | Entry | Late | TP | SL | Exit | Trades | Win | EV | Test win | Test EV | DD | PF | Conf | Min P | Min N | No low |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| top20 | 1h | double_corr | short | warn | next_bar_open | off | 1.618 | 0.750 | full | 28 | 96.4% | 6.01% | 100.0% | 6.64% | -5.1% | 34.09 | low | 60 | 0 | False |
| top20 | 1h | double_corr | short | none | next_bar_open | off | 1.618 | 0.750 | full | 28 | 96.4% | 6.01% | 100.0% | 6.64% | -5.1% | 34.09 | low | 50 | 0 | False |
| top20 | 1h | double_corr | short | none | next_bar_open | off | 1.618 | 0.750 | full | 28 | 96.4% | 6.01% | 100.0% | 6.64% | -5.1% | 34.09 | low | 65 | 0 | False |
| top20 | 1h | double_corr | short | warn | next_bar_open | off | 1.618 | 0.750 | full | 28 | 96.4% | 6.01% | 100.0% | 6.64% | -5.1% | 34.09 | low | 58 | 0 | False |
| top20 | 1h | double_corr | short | warn | next_bar_open | off | 1.618 | 0.750 | full | 28 | 96.4% | 6.01% | 100.0% | 6.64% | -5.1% | 34.09 | low | 65 | 0 | False |
| top20 | 1h | double_corr | short | none | next_bar_open | off | 1.618 | 0.750 | full | 28 | 96.4% | 6.01% | 100.0% | 6.64% | -5.1% | 34.09 | low | 55 | 0 | False |
| top20 | 1h | double_corr | short | warn | next_bar_open | off | 1.618 | 0.750 | full | 28 | 96.4% | 6.01% | 100.0% | 6.64% | -5.1% | 34.09 | low | 52 | 0 | False |
| top20 | 1h | double_corr | short | none | next_bar_open | off | 1.618 | 0.750 | full | 28 | 96.4% | 6.01% | 100.0% | 6.64% | -5.1% | 34.09 | low | 58 | 0 | False |
| top20 | 1h | double_corr | short | warn | next_bar_open | off | 1.618 | 0.750 | full | 28 | 96.4% | 6.01% | 100.0% | 6.64% | -5.1% | 34.09 | low | 55 | 0 | False |
| top20 | 1h | double_corr | short | none | next_bar_open | off | 1.618 | 0.750 | full | 28 | 96.4% | 6.01% | 100.0% | 6.64% | -5.1% | 34.09 | low | 60 | 0 | False |

## Recommended indicator defaults

- Crypto is research-only until `probability_calibration_crypto_v0.json` exists and passes Pine/Python parity.
- Main candidate patterns remain `flat` and `double_corr` fade only; do not reuse stock P(win) on crypto.
- Prefer `next_bar_open`/fresh signal behavior for practical alerts, but do not display stale entries after TP progress exceeds the selected late-entry limit.
- Treat missing calibration, low sample size, or low confidence as WAIT/research.

## Risks

- Crypto MVP uses Binance public klines; exchange-grade validation should still compare venues before Pine production defaults.
- Crypto trades 24/7; daily/weekly bar boundaries can differ by data source/timezone.
- Spot/perpetual futures must not share one calibration because funding, leverage and liquidation risk change EV.
- Same-bar TP/SL ambiguity is resolved conservatively by checking SL before TP.

## Files

- Trades: `/Users/DEV/Elliott-wave/python/data/historical_signal_grid_crypto_trades.parquet`
- JSON summary: `/Users/DEV/Elliott-wave/brain-output/signals/historical_signal_grid_crypto_summary.json`
