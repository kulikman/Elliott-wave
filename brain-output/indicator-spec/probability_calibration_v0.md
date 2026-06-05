# Probability Calibration v0

Generated: `2026-06-05T06:14:36+00:00`

Purpose: machine-readable calibration for indicator output fields `p_up`, `p_down`, `p_trade_win`, `expected_net_return`, `confidence` and `recommended_action`.

Source: `python/data/trades_sprint6.parquet`.

Important: this file calibrates probabilities from the stored sprint6 trade records. Use `docs/validation/sprint6-final.md` as the final portfolio baseline.

Lookup priority:

- `fig_type+interval+side`
- `fig_type+interval`
- `fig_type+side`
- `fig_type`

## fig_type+interval+side

| key | n | action | P(win) | P(up) | P(down) | EV | confidence |
|---|---:|---|---:|---:|---:|---:|---|
| `double_corr|1d|long` | 3 | buy | 100.0% | 100.0% | 0.0% | +8.78% | low |
| `double_corr|1d|short` | 1 | sell | 100.0% | 0.0% | 100.0% | +6.83% | low |
| `double_corr|1h|long` | 14 | buy | 78.6% | 78.6% | 21.4% | +0.83% | low |
| `double_corr|1h|short` | 15 | sell | 86.7% | 13.3% | 86.7% | +1.83% | low |
| `flat|1d|long` | 24 | buy | 66.7% | 66.7% | 33.3% | +2.19% | low |
| `flat|1d|short` | 23 | sell | 69.6% | 30.4% | 69.6% | +4.51% | low |
| `flat|1h|long` | 251 | buy | 55.4% | 55.4% | 44.6% | +0.41% | high |
| `flat|1h|short` | 233 | sell | 54.5% | 45.5% | 54.5% | +0.33% | high |
| `impulse|1d|long` | 5 | skip | 40.0% | 40.0% | 60.0% | -0.60% | low |
| `impulse|1d|short` | 31 | skip | 32.3% | 67.7% | 32.3% | -5.71% | low |
| `impulse|1h|long` | 202 | skip | 48.0% | 48.0% | 52.0% | +0.22% | high |
| `impulse|1h|short` | 217 | skip | 50.2% | 49.8% | 50.2% | -0.17% | high |
| `triangle|1d|long` | 160 | skip | 51.2% | 51.2% | 48.8% | +0.70% | high |
| `triangle|1d|short` | 159 | skip | 43.4% | 56.6% | 43.4% | -0.39% | high |
| `triangle|1h|long` | 1559 | skip | 40.0% | 40.0% | 60.0% | -0.18% | very_high |
| `triangle|1h|short` | 1385 | skip | 40.0% | 60.0% | 40.0% | -0.16% | very_high |

## fig_type+interval

| key | n | action | P(win) | P(up) | P(down) | EV | confidence |
|---|---:|---|---:|---:|---:|---:|---|
| `double_corr|1d` | 4 | wait | 100.0% | n/a | n/a | +8.30% | low |
| `double_corr|1h` | 29 | wait | 82.8% | n/a | n/a | +1.35% | low |
| `flat|1d` | 47 | wait | 68.1% | n/a | n/a | +3.33% | low |
| `flat|1h` | 484 | wait | 55.0% | n/a | n/a | +0.37% | very_high |
| `impulse|1d` | 36 | skip | 33.3% | n/a | n/a | -5.00% | low |
| `impulse|1h` | 419 | skip | 49.2% | n/a | n/a | +0.02% | very_high |
| `triangle|1d` | 319 | skip | 47.3% | n/a | n/a | +0.15% | high |
| `triangle|1h` | 2944 | skip | 40.0% | n/a | n/a | -0.17% | very_high |

## fig_type+side

| key | n | action | P(win) | P(up) | P(down) | EV | confidence |
|---|---:|---|---:|---:|---:|---:|---|
| `double_corr|long` | 17 | buy | 82.4% | 82.4% | 17.6% | +2.23% | low |
| `double_corr|short` | 16 | sell | 87.5% | 12.5% | 87.5% | +2.15% | low |
| `flat|long` | 275 | buy | 56.4% | 56.4% | 43.6% | +0.57% | high |
| `flat|short` | 256 | sell | 55.9% | 44.1% | 55.9% | +0.70% | high |
| `impulse|long` | 207 | skip | 47.8% | 47.8% | 52.2% | +0.21% | high |
| `impulse|short` | 248 | skip | 48.0% | 52.0% | 48.0% | -0.86% | high |
| `triangle|long` | 1719 | skip | 41.0% | 41.0% | 59.0% | -0.10% | very_high |
| `triangle|short` | 1544 | skip | 40.3% | 59.7% | 40.3% | -0.18% | very_high |

## fig_type

| key | n | action | P(win) | P(up) | P(down) | EV | confidence |
|---|---:|---|---:|---:|---:|---:|---|
| `double_corr` | 33 | wait | 84.8% | n/a | n/a | +2.19% | low |
| `flat` | 531 | wait | 56.1% | n/a | n/a | +0.63% | very_high |
| `impulse` | 455 | skip | 47.9% | n/a | n/a | -0.38% | very_high |
| `triangle` | 3263 | skip | 40.7% | n/a | n/a | -0.14% | very_high |
