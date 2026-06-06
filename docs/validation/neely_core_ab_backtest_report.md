# Neely Core A/B Backtest

Generated: `2026-06-06T13:32:19.168977+00:00`

Scope: top20 stocks and top20 crypto. Baseline A = current flat/double_corr fade. Core B = book-derived Neely signals with Fibonacci buckets.

## Run Summary

- Assets: `stocks, crypto`
- Intervals: `15m, 30m, 1h, 4h, 1d, 1w`
- Usable frames: `189` / `240`
- Trade rows: `23268`
- Stock provider: `tiingo-cache`
- Output trades: `/Users/DEV/Elliott-wave/python/data/neely_core_ab_backtest_trades.parquet`

## Data Coverage

| asset_class   | interval   |   requested |   ok |   missing |   trades |
|:--------------|:-----------|------------:|-----:|----------:|---------:|
| crypto        | 15m        |          20 |   20 |         0 |     6164 |
| crypto        | 1d         |          20 |   20 |         0 |      598 |
| crypto        | 1h         |          20 |   20 |         0 |     5981 |
| crypto        | 1w         |          20 |   20 |         0 |      133 |
| crypto        | 30m        |          20 |   20 |         0 |     6035 |
| crypto        | 4h         |          20 |   20 |         0 |     3102 |
| stocks        | 15m        |          20 |   20 |         0 |      428 |
| stocks        | 1d         |          20 |   20 |         0 |      376 |
| stocks        | 1h         |          20 |    3 |        17 |      141 |
| stocks        | 1w         |          20 |    3 |        17 |       28 |
| stocks        | 30m        |          20 |   20 |         0 |      222 |
| stocks        | 4h         |          20 |    3 |        17 |       60 |

## A/B Setup Results

| asset_class   | interval   | ab_group   | setup                         | fig_type    | side   |    n | winrate   | ev     | profit_factor   | max_drawdown   | tp_rate   | sl_rate   |
|:--------------|:-----------|:-----------|:------------------------------|:------------|:-------|-----:|:----------|:-------|:----------------|:---------------|:----------|:----------|
| crypto        | 1d         | A          | baseline_double_corr_fade     | double_corr | long   |    6 | 100.0%    | 38.13% | n/a             | 0.0%           | 83.3%     | 0.0%      |
| crypto        | 1w         | A          | baseline_flat_fade            | flat        | long   |    7 | 57.1%     | 29.03% | 4.65            | -48.5%         | 57.1%     | 28.6%     |
| crypto        | 1w         | B          | core_impulse_post_w4          | impulse     | long   |    8 | 75.0%     | 27.77% | 3.27            | -76.1%         | 75.0%     | 0.0%      |
| crypto        | 1w         | B          | core_triangle_thrust          | triangle    | long   |   50 | 66.0%     | 19.62% | 2.36            | -99.4%         | 46.0%     | 6.0%      |
| crypto        | 1d         | B          | core_moving_correction_follow | moving_corr | short  |   10 | 60.0%     | 16.06% | 3.91            | -21.6%         | 20.0%     | 40.0%     |
| crypto        | 1w         | A          | baseline_flat_fade            | flat        | short  |   10 | 70.0%     | 11.17% | 1.58            | -64.1%         | 40.0%     | 20.0%     |
| crypto        | 4h         | A          | baseline_double_corr_fade     | double_corr | long   |   12 | 91.7%     | 10.41% | 17.48           | -7.6%          | 66.7%     | 8.3%      |
| crypto        | 4h         | A          | baseline_double_corr_fade     | double_corr | short  |   11 | 90.9%     | 9.79%  | 11.64           | -10.1%         | 45.5%     | 0.0%      |
| crypto        | 1d         | B          | core_moving_correction_follow | moving_corr | long   |    8 | 37.5%     | 7.73%  | 2.66            | -25.6%         | 37.5%     | 62.5%     |
| crypto        | 1h         | A          | baseline_double_corr_fade     | double_corr | long   |   20 | 90.0%     | 5.70%  | 30.50           | -2.7%          | 40.0%     | 0.0%      |
| crypto        | 1h         | A          | baseline_double_corr_fade     | double_corr | short  |   28 | 96.4%     | 5.63%  | 24.55           | -6.7%          | 39.3%     | 3.6%      |
| crypto        | 1d         | A          | baseline_flat_fade            | flat        | short  |   26 | 69.2%     | 4.06%  | 1.88            | -33.3%         | 26.9%     | 23.1%     |
| crypto        | 1d         | A          | baseline_flat_fade            | flat        | long   |   27 | 55.6%     | 3.61%  | 1.42            | -63.7%         | 48.1%     | 22.2%     |
| crypto        | 30m        | A          | baseline_double_corr_fade     | double_corr | long   |   25 | 96.0%     | 3.43%  | 17.14           | -5.3%          | 44.0%     | 4.0%      |
| crypto        | 30m        | A          | baseline_double_corr_fade     | double_corr | short  |   33 | 84.8%     | 2.91%  | 4.36            | -12.0%         | 48.5%     | 12.1%     |
| crypto        | 15m        | A          | baseline_double_corr_fade     | double_corr | short  |   33 | 87.9%     | 2.43%  | 21.52           | -3.0%          | 54.5%     | 0.0%      |
| crypto        | 4h         | A          | baseline_flat_fade            | flat        | long   |  112 | 58.9%     | 2.17%  | 2.17            | -35.8%         | 34.8%     | 17.0%     |
| crypto        | 4h         | B          | core_moving_correction_follow | moving_corr | long   |   32 | 37.5%     | 2.13%  | 1.99            | -25.5%         | 28.1%     | 62.5%     |
| crypto        | 1d         | B          | core_triangle_thrust          | triangle    | short  |  182 | 64.3%     | 2.11%  | 1.30            | -99.4%         | 28.0%     | 20.9%     |
| crypto        | 1d         | B          | core_impulse_post_w4          | impulse     | long   |   73 | 64.4%     | 1.91%  | 1.28            | -93.1%         | 50.7%     | 4.1%      |
| crypto        | 4h         | B          | core_moving_correction_follow | moving_corr | short  |   49 | 36.7%     | 1.57%  | 1.75            | -24.5%         | 24.5%     | 63.3%     |
| crypto        | 4h         | B          | core_impulse_post_w4          | impulse     | long   |  333 | 67.0%     | 1.53%  | 1.61            | -65.0%         | 53.8%     | 11.7%     |
| crypto        | 15m        | A          | baseline_double_corr_fade     | double_corr | long   |   28 | 82.1%     | 1.32%  | 4.29            | -6.6%          | 53.6%     | 7.1%      |
| crypto        | 4h         | A          | baseline_flat_fade            | flat        | short  |  132 | 69.7%     | 1.29%  | 1.84            | -28.8%         | 29.5%     | 16.7%     |
| crypto        | 1h         | B          | core_moving_correction_follow | moving_corr | short  |   90 | 34.4%     | 0.62%  | 1.46            | -23.4%         | 26.7%     | 62.2%     |
| crypto        | 4h         | B          | core_triangle_thrust          | triangle    | short  | 1031 | 53.4%     | 0.46%  | 1.17            | -87.5%         | 24.9%     | 14.6%     |
| crypto        | 30m        | A          | baseline_flat_fade            | flat        | short  |  245 | 58.0%     | 0.42%  | 1.77            | -18.5%         | 38.0%     | 20.0%     |
| crypto        | 4h         | B          | core_triangle_thrust          | triangle    | long   | 1049 | 50.7%     | 0.36%  | 1.13            | -94.1%         | 28.1%     | 12.0%     |
| crypto        | 1h         | A          | baseline_flat_fade            | flat        | short  |  267 | 58.8%     | 0.24%  | 1.23            | -30.1%         | 32.2%     | 16.1%     |
| crypto        | 1h         | B          | core_moving_correction_follow | moving_corr | long   |   90 | 27.8%     | 0.22%  | 1.18            | -22.7%         | 21.1%     | 67.8%     |

## Fibonacci Probability Buckets

| asset_class   | interval   | setup                         | fig_type    | fib_primary_bucket   | fib_primary_near   |   n | winrate   | ev     | profit_factor   |
|:--------------|:-----------|:------------------------------|:------------|:---------------------|:-------------------|----:|:----------|:-------|:----------------|
| crypto        | 1w         | core_triangle_thrust          | triangle    | 2.618                | True               |   7 | 71.4%     | 45.73% | 4.24            |
| crypto        | 1d         | baseline_double_corr_fade     | double_corr | 0.5                  | True               |   7 | 100.0%    | 36.33% | n/a             |
| crypto        | 1w         | core_triangle_thrust          | triangle    | 2                    | True               |   7 | 85.7%     | 18.04% | 3.64            |
| crypto        | 1d         | core_moving_correction_follow | moving_corr | 1                    | True               |   7 | 42.9%     | 15.29% | 3.03            |
| crypto        | 4h         | baseline_double_corr_fade     | double_corr | 0.382                | True               |   6 | 100.0%    | 12.70% | n/a             |
| crypto        | 4h         | baseline_double_corr_fade     | double_corr | 0.5                  | True               |   7 | 85.7%     | 12.20% | 9.43            |
| crypto        | 1w         | core_triangle_thrust          | triangle    | 0.786                | True               |  10 | 40.0%     | 9.83%  | 1.51            |
| crypto        | 1d         | baseline_flat_fade            | flat        | off                  | False              |   7 | 71.4%     | 9.25%  | 2.44            |
| crypto        | 1w         | core_triangle_thrust          | triangle    | 1.272                | True               |   7 | 71.4%     | 8.70%  | 1.78            |
| crypto        | 1d         | baseline_flat_fade            | flat        | 1.382                | True               |   9 | 66.7%     | 7.58%  | 2.55            |
| crypto        | 1h         | baseline_double_corr_fade     | double_corr | 0.382                | True               |   8 | 100.0%    | 6.69%  | n/a             |
| crypto        | 1d         | baseline_flat_fade            | flat        | 1                    | True               |  10 | 70.0%     | 6.39%  | 2.65            |
| crypto        | 4h         | baseline_double_corr_fade     | double_corr | 0.618                | True               |   6 | 83.3%     | 6.37%  | 6.04            |
| crypto        | 1d         | core_impulse_post_w4          | impulse     | 1                    | True               |  13 | 76.9%     | 6.08%  | 2.09            |
| crypto        | 1h         | baseline_double_corr_fade     | double_corr | 0.618                | True               |  20 | 90.0%     | 5.70%  | 15.49           |
| crypto        | 1h         | baseline_double_corr_fade     | double_corr | 0.5                  | True               |  10 | 90.0%     | 5.41%  | 21.16           |
| crypto        | 1h         | baseline_double_corr_fade     | double_corr | off                  | False              |   9 | 100.0%    | 5.25%  | n/a             |
| crypto        | 1w         | core_impulse_post_w4          | impulse     | off                  | False              |  13 | 61.5%     | 4.73%  | 1.28            |
| crypto        | 30m        | baseline_double_corr_fade     | double_corr | off                  | False              |  16 | 93.8%     | 4.31%  | 6.75            |
| crypto        | 4h         | baseline_flat_fade            | flat        | 2                    | True               |  22 | 72.7%     | 4.17%  | 3.74            |
| crypto        | 1d         | core_impulse_post_w4          | impulse     | 1.382                | True               |  21 | 71.4%     | 4.04%  | 1.71            |
| crypto        | 4h         | core_impulse_post_w4          | impulse     | 0.786                | True               |  12 | 66.7%     | 3.90%  | 4.62            |
| crypto        | 4h         | core_moving_correction_follow | moving_corr | 1                    | True               |  14 | 42.9%     | 3.90%  | 2.78            |
| crypto        | 30m        | baseline_double_corr_fade     | double_corr | 0.382                | True               |  13 | 92.3%     | 3.54%  | 13.62           |
| crypto        | 4h         | baseline_flat_fade            | flat        | 1.382                | True               |  19 | 73.7%     | 3.17%  | 3.85            |
| crypto        | 1h         | core_impulse_post_w4          | impulse     | 0.618                | True               |  15 | 80.0%     | 3.11%  | 5.09            |
| crypto        | 4h         | baseline_flat_fade            | flat        | 2.618                | True               |  10 | 70.0%     | 2.69%  | 3.21            |
| crypto        | 15m        | baseline_double_corr_fade     | double_corr | 0.5                  | True               |  26 | 92.3%     | 2.57%  | 131.80          |
| crypto        | 4h         | core_moving_correction_follow | moving_corr | 0.786                | True               |  15 | 46.7%     | 2.55%  | 2.48            |
| crypto        | 4h         | baseline_flat_fade            | flat        | off                  | False              |  47 | 63.8%     | 2.38%  | 2.34            |

## Wave/Figure Probability

| asset_class   | interval   | fig_type    | direction   |    n | winrate   | ev     | profit_factor   | max_drawdown   |
|:--------------|:-----------|:------------|:------------|-----:|:----------|:-------|:----------------|:---------------|
| crypto        | 1d         | double_corr | down        |    6 | 100.0%    | 38.13% | n/a             | 0.0%           |
| crypto        | 1w         | flat        | down        |    7 | 57.1%     | 29.03% | 4.65            | -48.5%         |
| crypto        | 1w         | impulse     | down        |    8 | 75.0%     | 27.77% | 3.27            | -76.1%         |
| crypto        | 1w         | triangle    | down        |   50 | 66.0%     | 19.62% | 2.36            | -99.4%         |
| crypto        | 1d         | moving_corr | up          |   10 | 60.0%     | 16.06% | 3.91            | -21.6%         |
| crypto        | 1w         | flat        | up          |   10 | 70.0%     | 11.17% | 1.58            | -64.1%         |
| crypto        | 4h         | double_corr | down        |   12 | 91.7%     | 10.41% | 17.48           | -7.6%          |
| crypto        | 4h         | double_corr | up          |   11 | 90.9%     | 9.79%  | 11.64           | -10.1%         |
| crypto        | 1d         | moving_corr | down        |    8 | 37.5%     | 7.73%  | 2.66            | -25.6%         |
| crypto        | 1h         | double_corr | down        |   20 | 90.0%     | 5.70%  | 30.50           | -2.7%          |
| crypto        | 1h         | double_corr | up          |   28 | 96.4%     | 5.63%  | 24.55           | -6.7%          |
| crypto        | 1d         | flat        | up          |   26 | 69.2%     | 4.06%  | 1.88            | -33.3%         |
| crypto        | 1d         | flat        | down        |   27 | 55.6%     | 3.61%  | 1.42            | -63.7%         |
| crypto        | 30m        | double_corr | down        |   25 | 96.0%     | 3.43%  | 17.14           | -5.3%          |
| crypto        | 30m        | double_corr | up          |   33 | 84.8%     | 2.91%  | 4.36            | -12.0%         |
| crypto        | 15m        | double_corr | up          |   33 | 87.9%     | 2.43%  | 21.52           | -3.0%          |
| crypto        | 4h         | flat        | down        |  112 | 58.9%     | 2.17%  | 2.17            | -35.8%         |
| crypto        | 4h         | moving_corr | down        |   32 | 37.5%     | 2.13%  | 1.99            | -25.5%         |
| crypto        | 1d         | triangle    | up          |  182 | 64.3%     | 2.11%  | 1.30            | -99.4%         |
| crypto        | 1d         | impulse     | down        |   73 | 64.4%     | 1.91%  | 1.28            | -93.1%         |
| crypto        | 4h         | moving_corr | up          |   49 | 36.7%     | 1.57%  | 1.75            | -24.5%         |
| crypto        | 4h         | impulse     | down        |  333 | 67.0%     | 1.53%  | 1.61            | -65.0%         |
| crypto        | 15m        | double_corr | down        |   28 | 82.1%     | 1.32%  | 4.29            | -6.6%          |
| crypto        | 4h         | flat        | up          |  132 | 69.7%     | 1.29%  | 1.84            | -28.8%         |
| crypto        | 1h         | moving_corr | up          |   90 | 34.4%     | 0.62%  | 1.46            | -23.4%         |
| crypto        | 4h         | triangle    | up          | 1031 | 53.4%     | 0.46%  | 1.17            | -87.5%         |
| crypto        | 30m        | flat        | up          |  245 | 58.0%     | 0.42%  | 1.77            | -18.5%         |
| crypto        | 4h         | triangle    | down        | 1049 | 50.7%     | 0.36%  | 1.13            | -94.1%         |
| crypto        | 1h         | flat        | up          |  267 | 58.8%     | 0.24%  | 1.23            | -30.1%         |
| crypto        | 1h         | moving_corr | down        |   90 | 27.8%     | 0.22%  | 1.18            | -22.7%         |

## Interpretation Rules

- Do not promote a Core B signal to BUY/SELL unless it has positive EV, acceptable PF, and enough sample size out-of-sample in the next grid.
- Fibonacci buckets with `fib_primary_near=True` show whether classic ratios improved the setup probability.
- Crypto remains research-only unless its rows are stable separately from stock rows.
