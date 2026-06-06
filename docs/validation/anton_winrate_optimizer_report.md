# Anton Winrate Optimizer

Generated: `2026-06-06T13:46:59.874844+00:00`

Goal: increase signal winrate by filtering Elliott Wave setups, not by adding more trades.

## Formulas

- `winrate = wins / n`
- `EV = winrate * avg_win - (1 - winrate) * avg_loss`
- `breakeven_winrate = avg_loss / (avg_win + avg_loss)`
- `edge = winrate - breakeven_winrate`
- `profit_factor = gross_profit / abs(gross_loss)`
- `wilson_low` is used to penalize small samples.

## Run Summary

- Trades source: `/Users/DEV/Elliott-wave/python/data/neely_core_ab_backtest_trades.parquet`
- Rows: `23268`
- Split: chronological `70%` train / `30%` test per asset class
- Candidate filters tested: `119`
- Actionable profiles: `26`

## Anton High-Win Profiles

| asset_class   | interval   | setup                | fig_type   | side   | fib_primary_near   | rr_filter   | lag_filter   | amp_filter   |   train_n | train_winrate   | train_ev   |   test_n | test_winrate   | test_ev   |   test_profit_factor | test_breakeven_winrate   | test_edge_over_breakeven   |
|:--------------|:-----------|:---------------------|:-----------|:-------|:-------------------|:------------|:-------------|:-------------|----------:|:----------------|:-----------|---------:|:---------------|:----------|---------------------:|:-------------------------|:---------------------------|
| crypto        | 1h         | core_impulse_post_w4 | impulse    | short  | True               | <=0.75      | any          | >=3%         |       355 | 72.1%           | 0.2%       |       47 | 72.3%          | 0.4%      |                 1.47 | 64.0%                    | 8.4%                       |
| crypto        | 1h         | core_impulse_post_w4 | impulse    | short  | True               | <=0.75      | any          | >=2%         |       360 | 71.4%           | 0.1%       |       49 | 69.4%          | 0.3%      |                 1.46 | 60.8%                    | 8.6%                       |
| crypto        | 1h         | core_impulse_post_w4 | impulse    | short  | True               | <=0.75      | any          | any          |       360 | 71.4%           | 0.1%       |       50 | 68.0%          | 0.3%      |                 1.46 | 59.3%                    | 8.7%                       |
| crypto        | 1h         | core_impulse_post_w4 | impulse    | short  | True               | <=0.75      | any          | >=1%         |       360 | 71.4%           | 0.1%       |       50 | 68.0%          | 0.3%      |                 1.46 | 59.3%                    | 8.7%                       |
| crypto        | 1h         | baseline_flat_fade   | flat       | short  | True               | any         | any          | any          |       206 | 59.2%           | 0.4%       |       23 | 73.9%          | 0.4%      |                 1.64 | 63.3%                    | 10.6%                      |
| crypto        | 1h         | baseline_flat_fade   | flat       | short  | True               | <=1.0       | any          | any          |       201 | 59.2%           | 0.3%       |       23 | 73.9%          | 0.4%      |                 1.64 | 63.3%                    | 10.6%                      |
| crypto        | 1h         | baseline_flat_fade   | flat       | short  | True               | <=1.5       | any          | any          |       206 | 59.2%           | 0.4%       |       23 | 73.9%          | 0.4%      |                 1.64 | 63.3%                    | 10.6%                      |
| crypto        | 1h         | baseline_flat_fade   | flat       | short  | True               | >=1.0       | any          | any          |       199 | 59.3%           | 0.3%       |       23 | 73.9%          | 0.4%      |                 1.64 | 63.3%                    | 10.6%                      |
| crypto        | 1h         | baseline_flat_fade   | flat       | short  | True               | any         | <=10         | any          |       182 | 61.0%           | 0.3%       |       22 | 72.7%          | 0.3%      |                 1.49 | 64.1%                    | 8.6%                       |
| crypto        | 1h         | baseline_flat_fade   | flat       | short  | True               | <=1.0       | <=10         | any          |       177 | 61.0%           | 0.3%       |       22 | 72.7%          | 0.3%      |                 1.49 | 64.1%                    | 8.6%                       |
| crypto        | 1h         | baseline_flat_fade   | flat       | short  | True               | <=1.5       | <=10         | any          |       182 | 61.0%           | 0.3%       |       22 | 72.7%          | 0.3%      |                 1.49 | 64.1%                    | 8.6%                       |
| crypto        | 1h         | baseline_flat_fade   | flat       | short  | True               | >=1.0       | <=10         | any          |       175 | 61.1%           | 0.3%       |       22 | 72.7%          | 0.3%      |                 1.49 | 64.1%                    | 8.6%                       |
| crypto        | 4h         | core_triangle_thrust | triangle   | long   | True               | <=1.0       | <=10         | any          |       438 | 55.7%           | 0.6%       |       46 | 63.0%          | 0.7%      |                 1.37 | 55.5%                    | 7.6%                       |
| crypto        | 4h         | core_triangle_thrust | triangle   | long   | True               | <=1.5       | <=5          | >=1%         |       439 | 51.7%           | 0.4%       |       31 | 61.3%          | 1.3%      |                 1.75 | 47.4%                    | 13.8%                      |
| crypto        | 4h         | core_triangle_thrust | triangle   | long   | True               | <=1.5       | <=5          | >=2%         |       404 | 51.7%           | 0.4%       |       31 | 61.3%          | 1.3%      |                 1.75 | 47.4%                    | 13.8%                      |
| crypto        | 4h         | core_triangle_thrust | triangle   | long   | True               | <=1.0       | any          | any          |       473 | 55.2%           | 0.6%       |       49 | 61.2%          | 0.6%      |                 1.35 | 54.0%                    | 7.2%                       |
| crypto        | 4h         | core_triangle_thrust | triangle   | long   | True               | <=1.0       | <=10         | >=1%         |       404 | 55.7%           | 0.6%       |       42 | 61.9%          | 0.6%      |                 1.37 | 54.2%                    | 7.7%                       |
| crypto        | 4h         | core_triangle_thrust | triangle   | long   | True               | any         | <=5          | >=1%         |       513 | 50.9%           | 0.3%       |       33 | 60.6%          | 1.1%      |                 1.64 | 48.3%                    | 12.3%                      |
| crypto        | 4h         | core_triangle_thrust | triangle   | long   | True               | any         | <=5          | >=2%         |       474 | 50.8%           | 0.4%       |       33 | 60.6%          | 1.1%      |                 1.64 | 48.3%                    | 12.3%                      |
| crypto        | 4h         | core_triangle_thrust | triangle   | long   | True               | <=1.5       | <=5          | >=3%         |       377 | 52.3%           | 0.5%       |       30 | 60.0%          | 1.3%      |                 1.74 | 46.3%                    | 13.7%                      |

## Top Surviving Candidates

| asset_class   | interval   | setup                | fig_type   | side   | fib_primary_near   | rr_filter   | lag_filter   | amp_filter   |   train_n | train_winrate   | train_ev   |   test_n | test_winrate   | test_ev   |   test_profit_factor | test_breakeven_winrate   | test_edge_over_breakeven   |
|:--------------|:-----------|:---------------------|:-----------|:-------|:-------------------|:------------|:-------------|:-------------|----------:|:----------------|:-----------|---------:|:---------------|:----------|---------------------:|:-------------------------|:---------------------------|
| crypto        | 1h         | baseline_flat_fade   | flat       | short  | True               | any         | any          | any          |       206 | 59.2%           | 0.4%       |       23 | 73.9%          | 0.4%      |                 1.64 | 63.3%                    | 10.6%                      |
| crypto        | 1h         | baseline_flat_fade   | flat       | short  | True               | <=1.0       | any          | any          |       201 | 59.2%           | 0.3%       |       23 | 73.9%          | 0.4%      |                 1.64 | 63.3%                    | 10.6%                      |
| crypto        | 1h         | baseline_flat_fade   | flat       | short  | True               | <=1.5       | any          | any          |       206 | 59.2%           | 0.4%       |       23 | 73.9%          | 0.4%      |                 1.64 | 63.3%                    | 10.6%                      |
| crypto        | 1h         | baseline_flat_fade   | flat       | short  | True               | >=1.0       | any          | any          |       199 | 59.3%           | 0.3%       |       23 | 73.9%          | 0.4%      |                 1.64 | 63.3%                    | 10.6%                      |
| crypto        | 1h         | baseline_flat_fade   | flat       | short  | True               | any         | any          | >=1%         |       191 | 59.7%           | 0.4%       |       19 | 73.7%          | 0.5%      |                 1.64 | 63.0%                    | 10.6%                      |
| crypto        | 1h         | baseline_flat_fade   | flat       | short  | True               | <=1.0       | any          | >=1%         |       186 | 59.7%           | 0.3%       |       19 | 73.7%          | 0.5%      |                 1.64 | 63.0%                    | 10.6%                      |
| crypto        | 1h         | baseline_flat_fade   | flat       | short  | True               | <=1.5       | any          | >=1%         |       191 | 59.7%           | 0.4%       |       19 | 73.7%          | 0.5%      |                 1.64 | 63.0%                    | 10.6%                      |
| crypto        | 1h         | baseline_flat_fade   | flat       | short  | True               | >=1.0       | any          | >=1%         |       184 | 59.8%           | 0.4%       |       19 | 73.7%          | 0.5%      |                 1.64 | 63.0%                    | 10.6%                      |
| crypto        | 1h         | baseline_flat_fade   | flat       | short  | True               | any         | <=10         | any          |       182 | 61.0%           | 0.3%       |       22 | 72.7%          | 0.3%      |                 1.49 | 64.1%                    | 8.6%                       |
| crypto        | 1h         | baseline_flat_fade   | flat       | short  | True               | <=1.0       | <=10         | any          |       177 | 61.0%           | 0.3%       |       22 | 72.7%          | 0.3%      |                 1.49 | 64.1%                    | 8.6%                       |
| crypto        | 1h         | baseline_flat_fade   | flat       | short  | True               | <=1.5       | <=10         | any          |       182 | 61.0%           | 0.3%       |       22 | 72.7%          | 0.3%      |                 1.49 | 64.1%                    | 8.6%                       |
| crypto        | 1h         | baseline_flat_fade   | flat       | short  | True               | >=1.0       | <=10         | any          |       175 | 61.1%           | 0.3%       |       22 | 72.7%          | 0.3%      |                 1.49 | 64.1%                    | 8.6%                       |
| crypto        | 1h         | core_impulse_post_w4 | impulse    | short  | True               | <=0.75      | any          | >=3%         |       355 | 72.1%           | 0.2%       |       47 | 72.3%          | 0.4%      |                 1.47 | 64.0%                    | 8.4%                       |
| crypto        | 1h         | baseline_flat_fade   | flat       | short  | True               | any         | <=10         | >=1%         |       168 | 61.3%           | 0.4%       |       18 | 72.2%          | 0.4%      |                 1.48 | 63.7%                    | 8.5%                       |
| crypto        | 1h         | baseline_flat_fade   | flat       | short  | True               | <=1.0       | <=10         | >=1%         |       163 | 61.3%           | 0.3%       |       18 | 72.2%          | 0.4%      |                 1.48 | 63.7%                    | 8.5%                       |
| crypto        | 1h         | baseline_flat_fade   | flat       | short  | True               | <=1.5       | <=10         | >=1%         |       168 | 61.3%           | 0.4%       |       18 | 72.2%          | 0.4%      |                 1.48 | 63.7%                    | 8.5%                       |
| crypto        | 1h         | baseline_flat_fade   | flat       | short  | True               | >=1.0       | <=10         | >=1%         |       161 | 61.5%           | 0.4%       |       18 | 72.2%          | 0.4%      |                 1.48 | 63.7%                    | 8.5%                       |
| crypto        | 1h         | core_impulse_post_w4 | impulse    | short  | True               | <=0.75      | any          | >=2%         |       360 | 71.4%           | 0.1%       |       49 | 69.4%          | 0.3%      |                 1.46 | 60.8%                    | 8.6%                       |
| crypto        | 1h         | core_impulse_post_w4 | impulse    | short  | True               | <=0.75      | any          | any          |       360 | 71.4%           | 0.1%       |       50 | 68.0%          | 0.3%      |                 1.46 | 59.3%                    | 8.7%                       |
| crypto        | 1h         | core_impulse_post_w4 | impulse    | short  | True               | <=0.75      | any          | >=1%         |       360 | 71.4%           | 0.1%       |       50 | 68.0%          | 0.3%      |                 1.46 | 59.3%                    | 8.7%                       |
| crypto        | 4h         | core_triangle_thrust | triangle   | long   | True               | <=1.0       | <=5          | >=1%         |       294 | 55.8%           | 0.7%       |       25 | 64.0%          | 0.8%      |                 1.42 | 55.6%                    | 8.4%                       |
| crypto        | 4h         | core_triangle_thrust | triangle   | long   | True               | <=1.0       | <=5          | >=2%         |       269 | 56.1%           | 0.8%       |       25 | 64.0%          | 0.8%      |                 1.42 | 55.6%                    | 8.4%                       |
| crypto        | 4h         | core_triangle_thrust | triangle   | long   | True               | <=1.0       | <=5          | >=3%         |       246 | 56.9%           | 1.0%       |       25 | 64.0%          | 0.8%      |                 1.42 | 55.6%                    | 8.4%                       |
| crypto        | 4h         | core_triangle_thrust | triangle   | long   | True               | <=1.0       | <=10         | any          |       438 | 55.7%           | 0.6%       |       46 | 63.0%          | 0.7%      |                 1.37 | 55.5%                    | 7.6%                       |
| crypto        | 4h         | core_triangle_thrust | triangle   | long   | True               | <=1.0       | <=5          | any          |       316 | 56.3%           | 0.9%       |       27 | 63.0%          | 0.4%      |                 1.22 | 58.3%                    | 4.7%                       |
| crypto        | 4h         | core_triangle_thrust | triangle   | long   | True               | <=1.0       | <=10         | >=1%         |       404 | 55.7%           | 0.6%       |       42 | 61.9%          | 0.6%      |                 1.37 | 54.2%                    | 7.7%                       |
| crypto        | 4h         | core_triangle_thrust | triangle   | long   | True               | <=1.5       | <=5          | >=1%         |       439 | 51.7%           | 0.4%       |       31 | 61.3%          | 1.3%      |                 1.75 | 47.4%                    | 13.8%                      |
| crypto        | 4h         | core_triangle_thrust | triangle   | long   | True               | <=1.5       | <=5          | >=2%         |       404 | 51.7%           | 0.4%       |       31 | 61.3%          | 1.3%      |                 1.75 | 47.4%                    | 13.8%                      |
| crypto        | 4h         | core_triangle_thrust | triangle   | long   | True               | <=1.0       | any          | any          |       473 | 55.2%           | 0.6%       |       49 | 61.2%          | 0.6%      |                 1.35 | 54.0%                    | 7.2%                       |
| crypto        | 4h         | core_triangle_thrust | triangle   | long   | True               | <=1.0       | <=10         | >=2%         |       369 | 56.1%           | 0.6%       |       41 | 61.0%          | 0.5%      |                 1.26 | 55.3%                    | 5.7%                       |

## Interpretation

- Prefer fewer signals with `test_winrate >= 60%`, positive EV, PF >= 1.2, and edge above breakeven.
- Do not use raw winrate without EV; low-RR exits can win often and still be weak after costs.
- The best current profile is confluence: validated wave type + Fib proximity + RR/lag/amplitude gate.
