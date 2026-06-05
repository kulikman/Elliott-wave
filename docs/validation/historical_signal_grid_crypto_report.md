# Historical Signal Grid - Elliott Wave Brain

Generated: `2026-06-05T15:18:51.021985+00:00`

Scope: crypto only. Stocks, ETFs, FX and futures are excluded. Entry is evaluated on the figure confirmation bar or later; `next_bar_open` means the next 24/7 crypto bar open.

## Run scope

- Asset class: `crypto`.
- Requested universe modes: top20/top50/top100; executed max rank: `20`.
- Tickers with usable data: `20` / `20`.
- Base simulated rows after variants: `235649`.
- Timeframes: `15m, 30m, 1h, 4h, 1d, 1w`.
- Calibration source: `/Users/DEV/Elliott-wave/brain-output/indicator-spec/probability_calibration_crypto_v0.json`. If the crypto calibration file is missing, probability filters are disabled and the run is treated as uncalibrated research.

## Best winrate setups

| Universe | TF | Pattern | Side | MTF | Entry | Late | TP | SL | Exit | Trades | Win | EV | Test win | Test EV | DD | PF | Conf |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| top20 | 15m | double_corr | short | block_against_htf | next_bar_open | off | 0.500 | 0.750 | full | 30 | 100.0% | 1.77% | 100.0% | 1.29% | 0.0% | n/a | medium |
| top20 | 15m | double_corr | short | block_against_htf | next_bar_open | off | 0.500 | 1.000 | full | 30 | 100.0% | 1.77% | 100.0% | 1.29% | 0.0% | n/a | medium |
| top20 | 15m | double_corr | short | block_against_htf | next_bar_open | off | 0.500 | 1.250 | full | 30 | 100.0% | 1.77% | 100.0% | 1.29% | 0.0% | n/a | medium |
| top20 | 15m | double_corr | short | fade_not_against_htf | next_bar_open | off | 0.500 | 0.750 | full | 30 | 100.0% | 1.77% | 100.0% | 1.29% | 0.0% | n/a | medium |
| top20 | 15m | double_corr | short | fade_not_against_htf | next_bar_open | off | 0.500 | 1.000 | full | 30 | 100.0% | 1.77% | 100.0% | 1.29% | 0.0% | n/a | medium |
| top20 | 15m | double_corr | short | fade_not_against_htf | next_bar_open | off | 0.500 | 1.250 | full | 30 | 100.0% | 1.77% | 100.0% | 1.29% | 0.0% | n/a | medium |
| top20 | 15m | double_corr | short | long_only_htf_up_short_only_htf_down | next_bar_open | off | 0.500 | 0.750 | full | 30 | 100.0% | 1.77% | 100.0% | 1.29% | 0.0% | n/a | medium |
| top20 | 15m | double_corr | short | long_only_htf_up_short_only_htf_down | next_bar_open | off | 0.500 | 1.000 | full | 30 | 100.0% | 1.77% | 100.0% | 1.29% | 0.0% | n/a | medium |
| top20 | 15m | double_corr | short | long_only_htf_up_short_only_htf_down | next_bar_open | off | 0.500 | 1.250 | full | 30 | 100.0% | 1.77% | 100.0% | 1.29% | 0.0% | n/a | medium |
| top20 | 15m | double_corr | short | none | next_bar_open | off | 0.500 | 0.750 | full | 33 | 97.0% | 1.65% | 85.7% | 0.92% | -0.4% | 139.37 | medium |
| top20 | 15m | double_corr | short | none | next_bar_open | off | 0.500 | 1.000 | full | 33 | 97.0% | 1.65% | 85.7% | 0.92% | -0.4% | 139.37 | medium |
| top20 | 15m | double_corr | short | none | next_bar_open | off | 0.500 | 1.250 | full | 33 | 97.0% | 1.65% | 85.7% | 0.92% | -0.4% | 139.37 | medium |

## Best balanced setups

| Universe | TF | Pattern | Side | MTF | Entry | Late | TP | SL | Exit | Trades | Win | EV | Test win | Test EV | DD | PF | Conf |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| top20 | 4h | flat | long | block_against_htf | confirm_close | off | 1.000 | 0.750 | full | 56 | 57.1% | 3.27% | 41.7% | 0.14% | -19.6% | 2.84 | high |
| top20 | 4h | flat | long | fade_not_against_htf | confirm_close | off | 1.000 | 0.750 | full | 56 | 57.1% | 3.27% | 41.7% | 0.14% | -19.6% | 2.84 | high |
| top20 | 4h | flat | long | long_only_htf_up_short_only_htf_down | confirm_close | off | 1.000 | 0.750 | full | 56 | 57.1% | 3.27% | 41.7% | 0.14% | -19.6% | 2.84 | high |
| top20 | 30m | flat | short | long_only_htf_up_short_only_htf_down | confirm_close | off | 1.618 | 0.750 | full | 138 | 56.5% | 0.76% | 46.4% | 0.12% | -11.9% | 2.39 | high |
| top20 | 1h | flat | short | block_against_htf | confirm_close | off | 1.618 | 0.750 | full | 148 | 62.8% | 0.80% | 63.3% | 0.51% | -15.8% | 1.85 | high |
| top20 | 1h | flat | short | fade_not_against_htf | confirm_close | off | 1.618 | 0.750 | full | 148 | 62.8% | 0.80% | 63.3% | 0.51% | -15.8% | 1.85 | high |
| top20 | 1h | flat | short | block_against_htf | confirm_close | off | 1.618 | 0.750 | partial_50_100_1618 | 148 | 66.2% | 0.62% | 66.7% | 0.36% | -14.1% | 1.75 | high |
| top20 | 1h | flat | short | fade_not_against_htf | confirm_close | off | 1.618 | 0.750 | partial_50_100_1618 | 148 | 66.2% | 0.62% | 66.7% | 0.36% | -14.1% | 1.75 | high |
| top20 | 30m | flat | short | block_against_htf | confirm_close | off | 1.618 | 0.750 | full | 139 | 56.8% | 0.75% | 46.4% | 0.12% | -11.9% | 2.39 | high |
| top20 | 30m | flat | short | fade_not_against_htf | confirm_close | off | 1.618 | 0.750 | full | 139 | 56.8% | 0.75% | 46.4% | 0.12% | -11.9% | 2.39 | high |
| top20 | 1h | flat | short | long_only_htf_up_short_only_htf_down | confirm_close | off | 1.618 | 0.750 | full | 146 | 62.3% | 0.75% | 63.3% | 0.51% | -15.8% | 1.79 | high |
| top20 | 30m | flat | short | long_only_htf_up_short_only_htf_down | confirm_close | off | 1.618 | 1.000 | full | 138 | 58.0% | 0.73% | 46.4% | 0.00% | -14.8% | 2.25 | high |

## Setups to disable or keep as WAIT/research

| Universe | TF | Pattern | Side | MTF | Entry | Late | TP | SL | Exit | Trades | Win | EV | Test win | Test EV | DD | PF | Conf |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| top20 | 15m | flat | short | long_only_htf_up_short_only_htf_down | next_bar_open | off | 0.500 | 1.250 | full | 126 | 54.0% | -0.15% | 69.2% | 0.38% | -27.2% | 0.74 | low |
| top20 | 15m | flat | short | long_only_htf_up_short_only_htf_down | confirm_close | off | 0.500 | 1.250 | full | 126 | 54.0% | -0.15% | 69.2% | 0.39% | -27.3% | 0.74 | low |
| top20 | 15m | flat | short | none | next_bar_open | off | 0.500 | 1.250 | full | 262 | 55.7% | -0.14% | 64.2% | 0.18% | -39.2% | 0.71 | low |
| top20 | 15m | flat | short | warn | next_bar_open | off | 0.500 | 1.250 | full | 262 | 55.7% | -0.14% | 64.2% | 0.18% | -39.2% | 0.71 | low |
| top20 | 15m | flat | short | block_against_htf | next_bar_open | off | 0.500 | 1.250 | full | 128 | 54.7% | -0.13% | 69.2% | 0.38% | -26.6% | 0.76 | low |
| top20 | 15m | flat | short | fade_not_against_htf | next_bar_open | off | 0.500 | 1.250 | full | 128 | 54.7% | -0.13% | 69.2% | 0.38% | -26.6% | 0.76 | low |
| top20 | 15m | flat | short | block_against_htf | confirm_close | off | 0.500 | 1.250 | full | 128 | 54.7% | -0.13% | 69.2% | 0.39% | -26.7% | 0.76 | low |
| top20 | 15m | flat | short | fade_not_against_htf | confirm_close | off | 0.500 | 1.250 | full | 128 | 54.7% | -0.13% | 69.2% | 0.39% | -26.7% | 0.76 | low |
| top20 | 15m | flat | long | none | next_bar_open | off | 0.500 | 1.250 | full | 218 | 53.2% | -0.12% | 59.1% | 0.09% | -29.2% | 0.72 | low |
| top20 | 15m | flat | long | warn | next_bar_open | off | 0.500 | 1.250 | full | 218 | 53.2% | -0.12% | 59.1% | 0.09% | -29.2% | 0.72 | low |
| top20 | 15m | flat | long | block_against_htf | next_bar_open | off | 0.500 | 1.250 | full | 111 | 52.3% | -0.12% | 65.2% | 0.29% | -16.7% | 0.74 | low |
| top20 | 15m | flat | long | fade_not_against_htf | next_bar_open | off | 0.500 | 1.250 | full | 111 | 52.3% | -0.12% | 65.2% | 0.29% | -16.7% | 0.74 | low |

## Research only: impulse/triangle check

| Universe | TF | Pattern | Side | MTF | Entry | Late | TP | SL | Exit | Trades | Win | EV | Test win | Test EV | DD | PF | Conf |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| top20 | 1w | impulse | long | none | confirm_close | off | 1.000 | 1.000 | full | 31 | 74.2% | 54.53% | 42.9% | 16.41% | -86.2% | 6.11 | low |
| top20 | 1w | triangle | long | none | confirm_close | off | 1.000 | 1.000 | full | 51 | 43.1% | 6.09% | 9.1% | -37.41% | -99.6% | 1.38 | low |
| top20 | 1d | triangle | short | none | confirm_close | off | 1.000 | 1.000 | full | 184 | 63.6% | 2.01% | 78.4% | 10.89% | -99.4% | 1.31 | low |
| top20 | 4h | impulse | long | none | confirm_close | off | 1.000 | 1.000 | full | 370 | 47.0% | 1.17% | 31.1% | -4.95% | -92.4% | 1.26 | low |
| top20 | 4h | triangle | short | none | confirm_close | off | 1.000 | 1.000 | full | 1033 | 50.3% | 0.20% | 53.6% | 0.44% | -91.2% | 1.08 | low |
| top20 | 1d | impulse | long | none | confirm_close | off | 1.000 | 1.000 | full | 80 | 46.2% | 0.50% | 18.8% | -15.50% | -99.6% | 1.04 | low |
| top20 | 1d | triangle | long | none | confirm_close | off | 1.000 | 1.000 | full | 193 | 44.6% | 0.33% | 33.3% | -2.68% | -95.8% | 1.05 | low |
| top20 | 15m | impulse | short | none | confirm_close | off | 1.000 | 1.000 | full | 784 | 45.0% | -0.18% | 49.0% | 0.02% | -85.5% | 0.83 | low |
| top20 | 30m | impulse | long | none | confirm_close | off | 1.000 | 1.000 | full | 680 | 42.6% | -0.21% | 37.5% | -0.58% | -89.5% | 0.87 | low |
| top20 | 4h | triangle | long | none | confirm_close | off | 1.000 | 1.000 | full | 1058 | 44.7% | -0.05% | 41.5% | -0.61% | -98.4% | 0.98 | low |
| top20 | 1h | triangle | short | none | confirm_close | off | 1.000 | 1.000 | full | 1958 | 47.3% | -0.13% | 48.2% | -0.02% | -98.0% | 0.91 | low |
| top20 | 1h | triangle | long | none | confirm_close | off | 1.000 | 1.000 | full | 1938 | 46.5% | -0.22% | 43.3% | -0.31% | -99.6% | 0.85 | low |

## Probability filter observations

| Universe | TF | Pattern | Side | MTF | Entry | Late | TP | SL | Exit | Trades | Win | EV | Test win | Test EV | DD | PF | Conf | Min P | Min N | No low |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| top20 | 1h | double_corr | long | warn | confirm_close | off | 1.618 | 1.000 | full | 20 | 90.0% | 6.46% | 100.0% | 4.40% | -2.7% | 34.45 | low | 58 | 0 | False |
| top20 | 1h | double_corr | long | none | confirm_close | off | 1.618 | 0.750 | full | 20 | 90.0% | 6.46% | 100.0% | 4.40% | -2.7% | 34.45 | low | 65 | 0 | False |
| top20 | 1h | double_corr | long | warn | confirm_close | off | 1.618 | 1.000 | full | 20 | 90.0% | 6.46% | 100.0% | 4.40% | -2.7% | 34.45 | low | 55 | 0 | False |
| top20 | 1h | double_corr | long | warn | confirm_close | off | 1.618 | 1.250 | full | 20 | 90.0% | 6.46% | 100.0% | 4.40% | -2.7% | 34.45 | low | 52 | 0 | False |
| top20 | 1h | double_corr | long | warn | confirm_close | off | 1.618 | 1.000 | full | 20 | 90.0% | 6.46% | 100.0% | 4.40% | -2.7% | 34.45 | low | 52 | 0 | False |
| top20 | 1h | double_corr | long | warn | confirm_close | off | 1.618 | 1.250 | full | 20 | 90.0% | 6.46% | 100.0% | 4.40% | -2.7% | 34.45 | low | 55 | 0 | False |
| top20 | 1h | double_corr | long | warn | confirm_close | off | 1.618 | 0.750 | full | 20 | 90.0% | 6.46% | 100.0% | 4.40% | -2.7% | 34.45 | low | 52 | 0 | False |
| top20 | 1h | double_corr | long | none | confirm_close | off | 1.618 | 1.250 | full | 20 | 90.0% | 6.46% | 100.0% | 4.40% | -2.7% | 34.45 | low | 52 | 0 | False |
| top20 | 1h | double_corr | long | none | confirm_close | off | 1.618 | 1.000 | full | 20 | 90.0% | 6.46% | 100.0% | 4.40% | -2.7% | 34.45 | low | 52 | 0 | False |
| top20 | 1h | double_corr | long | warn | confirm_close | off | 1.618 | 1.250 | full | 20 | 90.0% | 6.46% | 100.0% | 4.40% | -2.7% | 34.45 | low | 58 | 0 | False |

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
