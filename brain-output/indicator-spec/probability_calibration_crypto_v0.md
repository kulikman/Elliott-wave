# Probability Calibration v0 — crypto

Generated: `2026-06-05T15:19:06+00:00`

Purpose: machine-readable calibration for indicator output fields `p_up`, `p_down`, `p_trade_win`, `expected_net_return`, `confidence` and `recommended_action`.

Asset class: `crypto`.
Source: `python/data/historical_signal_grid_crypto_trades.parquet`.

Important: do not mix this calibration with another asset class inside Pine.

Lookup priority:

- `fig_type+interval+side`
- `fig_type+interval`
- `fig_type+side`
- `fig_type`

## fig_type+interval+side

| key | n | action | P(win) | P(up) | P(down) | EV | confidence |
|---|---:|---|---:|---:|---:|---:|---|
| `double_corr|15m|long` | 28 | buy | 78.6% | 78.6% | 21.4% | +1.18% | low |
| `double_corr|15m|short` | 33 | sell | 90.9% | 9.1% | 90.9% | +2.34% | low |
| `double_corr|1d|long` | 6 | buy | 100.0% | 100.0% | 0.0% | +37.91% | low |
| `double_corr|1d|short` | 4 | sell | 100.0% | 0.0% | 100.0% | +27.20% | low |
| `double_corr|1h|long` | 20 | buy | 85.0% | 85.0% | 15.0% | +5.70% | low |
| `double_corr|1h|short` | 28 | sell | 96.4% | 3.6% | 96.4% | +5.66% | low |
| `double_corr|1w|short` | 1 | sell | 100.0% | 0.0% | 100.0% | +75.54% | low |
| `double_corr|30m|long` | 26 | buy | 88.5% | 88.5% | 11.5% | +3.42% | low |
| `double_corr|30m|short` | 33 | sell | 84.8% | 15.2% | 84.8% | +2.86% | low |
| `double_corr|4h|long` | 12 | buy | 91.7% | 91.7% | 8.3% | +11.02% | low |
| `double_corr|4h|short` | 10 | sell | 90.0% | 10.0% | 90.0% | +9.87% | low |
| `flat|15m|long` | 218 | buy | 49.5% | 49.5% | 50.5% | +0.07% | high |
| `flat|15m|short` | 262 | sell | 53.1% | 46.9% | 53.1% | +0.08% | high |
| `flat|1d|long` | 26 | buy | 53.8% | 53.8% | 46.2% | +3.59% | low |
| `flat|1d|short` | 27 | sell | 66.7% | 33.3% | 66.7% | +3.38% | low |
| `flat|1h|long` | 226 | buy | 54.0% | 54.0% | 46.0% | +0.24% | high |
| `flat|1h|short` | 269 | sell | 60.2% | 39.8% | 60.2% | +0.31% | high |
| `flat|1w|long` | 7 | buy | 57.1% | 57.1% | 42.9% | +28.76% | low |
| `flat|1w|short` | 10 | sell | 60.0% | 40.0% | 60.0% | -0.54% | low |
| `flat|30m|long` | 250 | buy | 54.8% | 54.8% | 45.2% | +0.21% | high |
| `flat|30m|short` | 245 | sell | 56.3% | 43.7% | 56.3% | +0.44% | high |
| `flat|4h|long` | 111 | buy | 59.5% | 59.5% | 40.5% | +1.76% | medium |
| `flat|4h|short` | 131 | sell | 69.5% | 30.5% | 69.5% | +1.31% | medium |

## fig_type+interval

| key | n | action | P(win) | P(up) | P(down) | EV | confidence |
|---|---:|---|---:|---:|---:|---:|---|
| `double_corr|15m` | 61 | wait | 85.2% | n/a | n/a | +1.81% | medium |
| `double_corr|1d` | 10 | wait | 100.0% | n/a | n/a | +33.63% | low |
| `double_corr|1h` | 48 | wait | 91.7% | n/a | n/a | +5.68% | low |
| `double_corr|1w` | 1 | wait | 100.0% | n/a | n/a | +75.54% | low |
| `double_corr|30m` | 59 | wait | 86.4% | n/a | n/a | +3.11% | medium |
| `double_corr|4h` | 22 | wait | 90.9% | n/a | n/a | +10.50% | low |
| `flat|15m` | 480 | wait | 51.5% | n/a | n/a | +0.07% | very_high |
| `flat|1d` | 53 | wait | 60.4% | n/a | n/a | +3.49% | medium |
| `flat|1h` | 495 | wait | 57.4% | n/a | n/a | +0.28% | very_high |
| `flat|1w` | 17 | wait | 58.8% | n/a | n/a | +11.53% | low |
| `flat|30m` | 495 | wait | 55.6% | n/a | n/a | +0.33% | very_high |
| `flat|4h` | 242 | wait | 64.9% | n/a | n/a | +1.52% | high |

## fig_type+side

| key | n | action | P(win) | P(up) | P(down) | EV | confidence |
|---|---:|---|---:|---:|---:|---:|---|
| `double_corr|long` | 92 | buy | 85.9% | 85.9% | 14.1% | +6.47% | medium |
| `double_corr|short` | 109 | sell | 90.8% | 9.2% | 90.8% | +5.62% | medium |
| `flat|long` | 838 | buy | 53.8% | 53.8% | 46.2% | +0.73% | very_high |
| `flat|short` | 944 | sell | 58.7% | 41.3% | 58.7% | +0.50% | very_high |

## fig_type

| key | n | action | P(win) | P(up) | P(down) | EV | confidence |
|---|---:|---|---:|---:|---:|---:|---|
| `double_corr` | 201 | wait | 88.6% | n/a | n/a | +6.01% | high |
| `flat` | 1782 | wait | 56.4% | n/a | n/a | +0.61% | very_high |
