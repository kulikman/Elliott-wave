# Probability Calibration v0 — crypto

Generated: `2026-06-05T14:20:49+00:00`

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
| `double_corr|15m|short` | 1 | sell | 100.0% | 0.0% | 100.0% | +2.46% | low |
| `double_corr|1d|long` | 4 | buy | 100.0% | 100.0% | 0.0% | +49.10% | low |
| `double_corr|1d|short` | 3 | sell | 100.0% | 0.0% | 100.0% | +27.53% | low |
| `double_corr|1h|long` | 1 | buy | 100.0% | 100.0% | 0.0% | +3.21% | low |
| `double_corr|1w|short` | 1 | sell | 100.0% | 0.0% | 100.0% | +75.54% | low |
| `double_corr|30m|long` | 1 | buy | 0.0% | 0.0% | 100.0% | -2.37% | low |
| `double_corr|30m|short` | 2 | sell | 50.0% | 50.0% | 50.0% | +1.22% | low |
| `double_corr|4h|long` | 2 | buy | 100.0% | 100.0% | 0.0% | +13.45% | low |
| `double_corr|4h|short` | 1 | sell | 100.0% | 0.0% | 100.0% | +2.03% | low |
| `flat|15m|long` | 17 | buy | 41.2% | 41.2% | 58.8% | +0.20% | low |
| `flat|15m|short` | 9 | sell | 100.0% | 0.0% | 100.0% | +1.64% | low |
| `flat|1d|long` | 15 | buy | 46.7% | 46.7% | 53.3% | -3.24% | low |
| `flat|1d|short` | 17 | sell | 70.6% | 29.4% | 70.6% | +4.54% | low |
| `flat|1h|long` | 11 | buy | 36.4% | 36.4% | 63.6% | -0.57% | low |
| `flat|1h|short` | 20 | sell | 80.0% | 20.0% | 80.0% | +1.49% | low |
| `flat|1w|long` | 7 | buy | 57.1% | 57.1% | 42.9% | +28.76% | low |
| `flat|1w|short` | 11 | sell | 54.5% | 45.5% | 54.5% | -9.54% | low |
| `flat|30m|long` | 13 | buy | 46.2% | 46.2% | 53.8% | -0.09% | low |
| `flat|30m|short` | 12 | sell | 75.0% | 25.0% | 75.0% | +1.26% | low |
| `flat|4h|long` | 9 | buy | 55.6% | 55.6% | 44.4% | +1.55% | low |
| `flat|4h|short` | 15 | sell | 80.0% | 20.0% | 80.0% | +2.43% | low |

## fig_type+interval

| key | n | action | P(win) | P(up) | P(down) | EV | confidence |
|---|---:|---|---:|---:|---:|---:|---|
| `double_corr|15m` | 1 | wait | 100.0% | n/a | n/a | +2.46% | low |
| `double_corr|1d` | 7 | wait | 100.0% | n/a | n/a | +39.85% | low |
| `double_corr|1h` | 1 | wait | 100.0% | n/a | n/a | +3.21% | low |
| `double_corr|1w` | 1 | wait | 100.0% | n/a | n/a | +75.54% | low |
| `double_corr|30m` | 3 | wait | 33.3% | n/a | n/a | +0.02% | low |
| `double_corr|4h` | 3 | wait | 100.0% | n/a | n/a | +9.64% | low |
| `flat|15m` | 26 | wait | 61.5% | n/a | n/a | +0.70% | low |
| `flat|1d` | 32 | wait | 59.4% | n/a | n/a | +0.89% | low |
| `flat|1h` | 31 | wait | 64.5% | n/a | n/a | +0.76% | low |
| `flat|1w` | 18 | wait | 55.6% | n/a | n/a | +5.35% | low |
| `flat|30m` | 25 | wait | 60.0% | n/a | n/a | +0.56% | low |
| `flat|4h` | 24 | wait | 70.8% | n/a | n/a | +2.10% | low |

## fig_type+side

| key | n | action | P(win) | P(up) | P(down) | EV | confidence |
|---|---:|---|---:|---:|---:|---:|---|
| `double_corr|long` | 8 | buy | 87.5% | 87.5% | 12.5% | +28.02% | low |
| `double_corr|short` | 8 | sell | 87.5% | 12.5% | 87.5% | +20.63% | low |
| `flat|long` | 72 | buy | 45.8% | 45.8% | 54.2% | +2.26% | medium |
| `flat|short` | 84 | sell | 76.2% | 23.8% | 76.2% | +0.81% | medium |

## fig_type

| key | n | action | P(win) | P(up) | P(down) | EV | confidence |
|---|---:|---|---:|---:|---:|---:|---|
| `double_corr` | 16 | wait | 87.5% | n/a | n/a | +24.32% | low |
| `flat` | 156 | wait | 62.2% | n/a | n/a | +1.48% | high |
