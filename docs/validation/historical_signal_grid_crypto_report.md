# Historical Signal Grid - Elliott Wave Brain

Generated: `2026-06-05T14:07:58.102130+00:00`

Scope: crypto only. Stocks, ETFs, FX and futures are excluded. Entry is evaluated on the figure confirmation bar or later; `next_bar_open` means the next 24/7 crypto bar open.

## Run scope

- Asset class: `crypto`.
- Requested universe modes: top20/top50/top100; executed max rank: `20`.
- Tickers with usable data: `20` / `20`.
- Base simulated rows after variants: `19824`.
- Timeframes: `15m, 30m, 1h, 4h, 1d, 1w`.
- Calibration source: `/Users/DEV/Elliott-wave/brain-output/indicator-spec/probability_calibration_crypto_v0.json`. If the crypto calibration file is missing, probability filters are disabled and the run is treated as uncalibrated research.

## Best winrate setups

| Universe | TF | Pattern | Side | MTF | Entry | Late | TP | SL | Exit | Trades | Win | EV | Test win | Test EV | DD | PF | Conf |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|

## Best balanced setups

| Universe | TF | Pattern | Side | MTF | Entry | Late | TP | SL | Exit | Trades | Win | EV | Test win | Test EV | DD | PF | Conf |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|

## Setups to disable or keep as WAIT/research

| Universe | TF | Pattern | Side | MTF | Entry | Late | TP | SL | Exit | Trades | Win | EV | Test win | Test EV | DD | PF | Conf |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|

## Research only: impulse/triangle check

| Universe | TF | Pattern | Side | MTF | Entry | Late | TP | SL | Exit | Trades | Win | EV | Test win | Test EV | DD | PF | Conf |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| top20 | 1w | impulse | long | none | confirm_close | off | 1.000 | 1.000 | full | 31 | 71.0% | 54.64% | 28.6% | 4.87% | -86.2% | 5.98 | low |
| top20 | 4h | impulse | short | none | confirm_close | off | 1.000 | 1.000 | full | 52 | 67.3% | 5.19% | 100.0% | 9.42% | -39.2% | 3.22 | low |
| top20 | 1h | impulse | short | none | confirm_close | off | 1.000 | 1.000 | full | 41 | 73.2% | 2.87% | 100.0% | 8.46% | -8.7% | 4.51 | medium |
| top20 | 1w | triangle | long | none | confirm_close | off | 1.000 | 1.000 | full | 48 | 43.8% | 6.48% | 20.0% | -30.04% | -99.6% | 1.40 | low |
| top20 | 1d | impulse | short | none | confirm_close | off | 1.000 | 1.000 | full | 43 | 67.4% | 4.51% | 33.3% | 2.30% | -81.7% | 1.67 | low |
| top20 | 1d | triangle | short | none | confirm_close | off | 1.000 | 1.000 | full | 112 | 64.3% | 3.99% | 91.3% | 16.00% | -88.0% | 1.65 | low |
| top20 | 15m | impulse | short | none | confirm_close | off | 1.000 | 1.000 | full | 65 | 49.2% | 0.51% | 84.6% | 2.24% | -10.1% | 1.57 | medium |
| top20 | 1h | triangle | short | none | confirm_close | off | 1.000 | 1.000 | full | 123 | 52.8% | 0.14% | 80.0% | 1.04% | -14.8% | 1.16 | low |
| top20 | 15m | triangle | short | none | confirm_close | off | 1.000 | 1.000 | full | 129 | 48.8% | 0.07% | 53.8% | 0.79% | -17.3% | 1.15 | low |
| top20 | 30m | triangle | short | none | confirm_close | off | 1.000 | 1.000 | full | 145 | 50.3% | 0.13% | 65.5% | 1.07% | -21.6% | 1.20 | low |
| top20 | 4h | triangle | short | none | confirm_close | off | 1.000 | 1.000 | full | 113 | 54.0% | 0.31% | 56.5% | 1.82% | -40.7% | 1.18 | low |
| top20 | 30m | impulse | short | none | confirm_close | off | 1.000 | 1.000 | full | 56 | 41.1% | -0.02% | 83.3% | 2.54% | -26.9% | 0.98 | low |

## Probability filter observations

| Universe | TF | Pattern | Side | MTF | Entry | Late | TP | SL | Exit | Trades | Win | EV | Test win | Test EV | DD | PF | Conf | Min P | Min N | No low |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| top20 | 1h | flat | short | none | confirm_close | off | 1.618 | 1.250 | full | 20 | 80.0% | 1.93% | 100.0% | 5.30% | -3.8% | 6.36 | low | 55 | 100 | True |
| top20 | 1h | flat | short | none | confirm_close | off | 1.618 | 1.250 | full | 20 | 80.0% | 1.93% | 100.0% | 5.30% | -3.8% | 6.36 | low | 60 | 0 | True |
| top20 | 1h | flat | short | none | confirm_close | off | 1.618 | 1.250 | full | 20 | 80.0% | 1.93% | 100.0% | 5.30% | -3.8% | 6.36 | low | 60 | 50 | True |
| top20 | 1h | flat | short | warn | confirm_close | off | 1.618 | 1.250 | full | 20 | 80.0% | 1.93% | 100.0% | 5.30% | -3.8% | 6.36 | low | 52 | 100 | True |
| top20 | 1h | flat | short | warn | confirm_close | off | 1.618 | 1.250 | full | 20 | 80.0% | 1.93% | 100.0% | 5.30% | -3.8% | 6.36 | low | 60 | 50 | False |
| top20 | 1h | flat | short | none | confirm_close | off | 1.618 | 1.250 | full | 20 | 80.0% | 1.93% | 100.0% | 5.30% | -3.8% | 6.36 | low | 55 | 0 | False |
| top20 | 1h | flat | short | none | confirm_close | off | 1.618 | 1.250 | full | 20 | 80.0% | 1.93% | 100.0% | 5.30% | -3.8% | 6.36 | low | 60 | 50 | False |
| top20 | 1h | flat | short | warn | confirm_close | off | 1.618 | 1.250 | full | 20 | 80.0% | 1.93% | 100.0% | 5.30% | -3.8% | 6.36 | low | 60 | 30 | True |
| top20 | 1h | flat | short | warn | confirm_close | off | 1.618 | 1.250 | full | 20 | 80.0% | 1.93% | 100.0% | 5.30% | -3.8% | 6.36 | low | 55 | 0 | False |
| top20 | 1h | flat | short | none | confirm_close | off | 1.618 | 1.250 | full | 20 | 80.0% | 1.93% | 100.0% | 5.30% | -3.8% | 6.36 | low | 60 | 30 | True |

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
