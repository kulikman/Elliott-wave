# Neely Book Reaudit for Indicator and Tests

Date: 2026-06-06

Scope: this is a source-first reaudit of the collected book data for `Elliott Wave Brain - Monowaves MTF`. It treats the AKU/spec as if we had just extracted the books and were designing the indicator and historical tests from scratch.

Sources reviewed:

- `brain-output/indicator-spec/spec_v3.0.json`
- `brain-output/indicator-spec/neely-algorithm-L1-L3.md`
- `brain-output/kb/*.md`
- `aku/neely-mwe-1990/**/AKU-*.yaml`
- `aku/intraday-*/**/AKU-*.yaml`
- `pine/ewb_monowaves_mtf.pine`
- `python/ewb/*.py`
- `python/scripts/historical_signal_grid.py`

## Main Finding

The previous audit was too bound to the current trade layer: `flat` and `double_corr` fade, probability, entry, stop, target. That is useful for a v0 trading assistant, but it is not the full book-derived Neely workflow.

If we build from the books, the core should be:

1. identify monowaves;
2. classify every monowave with Rule 1-7 and condition a-f;
3. assign structural labels and position indicators;
4. group only valid 3-wave or 5-wave same-degree units;
5. compact confirmed groups into `:3` or `:5`;
6. validate patterns with impulse/zigzag/flat/triangle/terminal rules;
7. apply channels, formal logic, energy rating, time rules, and post-pattern effects;
8. align the current wave with the active higher-timeframe wave/degree;
9. only then decide `BUY`, `SELL`, `WAIT`, `TP`, `SL`, and invalidation.

The current Pine/Python code has pieces of this, but the trading decision does not yet use most of the book pipeline.

## Chapter Map

| Source chapter | Indicator role | Interaction that matters | Current status |
|---|---|---|---|
| Neely ch.2, basic concepts | Defines monowave, impulse/correction class, `:5`/`:3`, degree | Every later wave type is built from monowaves and relative degree, not isolated pivot shapes | Implemented as zigzag/monowave detection, but degree is still shallow |
| Neely ch.3, preliminary analysis | Rule Determiner, conditions a-f, structural lists, position indicators | A monowave is not just up/down; its next/previous waves classify it and restrict legal roles | Implemented partly in `rules.py`/Pine, but position indicators barely affect trading |
| Neely ch.4, grouping | Structural Series A-E, grouping by 3/5, compaction, zigzag-vs-impulse priority | A figure must be a group of same-degree waves, then compacted and reassessed | Pine has optional figure recognition/compaction; Python has greedy figures, not full recursive grouping |
| Neely ch.5, core pattern rules | Impulse, zigzag, flat, triangle, terminal constraints | Figure type changes expected next movement and invalidation level | Confirmations exist for basic geometry, but not all rules are action gates |
| Neely ch.6, formal logic | Confirmation after pattern completion | Entry should often wait for trendline break/reach rules, not only pivot confirmation | Mostly absent from Action now |
| Neely ch.8, complex waves | x-waves, double/triple zigzags, combinations, multiwaves, complexity | Double correction is not just three pivots; x-wave size/complexity controls parent correction | Current `double_corr` is a useful approximation, but not a true x-wave engine |
| Neely ch.9, extensions | Channels, time inequality, exception logic, full workflow | Channel shape distinguishes impulse vs correction and confirms completion | Pine has partial channel/time functions; trading does not depend on them |
| Neely ch.10, advanced logic | Energy rating and post-pattern effects | Gives target/retrace expectations after completed patterns | Energy is visual/partial; targets still mostly figure-amplitude based |
| Neely ch.11, motion labels | Motion labels are last, and positions restrict pattern types | Waves 2/4/b/d/e/x cannot be impulses; labels should follow structural proof | This is a high-priority missing filter |
| Neely ch.12, extra extensions | Channel confirmation, Fibonacci internals, missing waves, reverse logic | Multi-interpretation should reduce confidence or force WAIT | Partly unimplemented; should become scoring/WAIT logic |
| Intraday L01, 3 touches | Practical channel/arc completion hint | Third touch can mark completion/reversal candidates | Draft/review only; do not gate signals yet |
| Intraday L02, positive lock | Position management idea | Multiple entries/locking profit after structure | Out of scope for single-entry indicator v1 |
| Intraday L03, S-curves | Extended 3rd impulse and retracement context | S-curve location changes expected retrace: trend continuation vs full reversal | Useful as research feature after impulse-extension detection |
| Intraday L04, Stella | Extended 5th impulse | Can warn about late trend/end-of-trend behavior | Useful for terminal/extended-5 diagnostics |
| Intraday L05, VAL | Extended 1st impulse | Interacts with 3-touch and strong retracement | Useful for impulse subtype diagnostics |
| Intraday L06, ellipses | Zigzag framing and C ~= A observation | Gives practical target/entry zones around zigzag completion | Research only until formalized/tested |
| Intraday L07, moving correction | Running/moving correction | After moving correction, next impulse should be >161.8% of prior impulse | High-value target logic, but AKU are draft/review |
| Intraday L08, fractal dimension shift | Degree shift | Best entries may occur when smaller fractal completes and larger starts | Aligns with MTF-degree work |
| Intraday L09, PTV/time growth | Price-time projection | Adds time target and reversal timing, not just price target | Research-only until verified |
| Intraday L10, trading technique | Stop placement and news exception | Stop must be based on forecasted figure invalidation, with special news exception | Do not hardcode 8-10 points; asset-dependent |

## Wave Interaction Map

| Wave/type | Book-derived role | Must interact with | Testing implication |
|---|---|---|---|
| Monowave | Atomic wave from one direction change to next | Neighboring monowaves `m0/m1/m2/m3` | Test pivot sensitivity and confirmation lag |
| `:5` | Impulse-class structural unit | Position labels, impulse rules, channels | Do not label every directional move as tradable impulse |
| `:3` | Corrective-class structural unit | Flats, zigzags, triangles, x-waves | Corrections should drive fade/follow logic differently by subtype |
| `:F3` | First corrective segment | `:c3`, x-wave, `:5` boundaries | Needed to know whether a correction is beginning or nested |
| `:c3` | Center corrective segment | Cannot be first or last | If current bar is inside `:c3`, strong action should usually be WAIT |
| `:sL3` and `:L3` | Pre-terminal / terminal corrective positions | Triangle/terminal distinction | Needed to show what wave the last bar is inside |
| `:L5` | Last impulse unit completing a figure | Zigzag vs impulse ambiguity | Must check impulse hypothesis before accepting zigzag |
| Impulse | Trend/terminal pattern, 5 segments | Alternation, extension, overlap, 0-2/2-4 channels, higher degree | Use as context/follow only after post-pattern confirmation; not raw fade |
| Terminal impulse | Ending 5-wave with overlap | Must retrace to start quickly | Strong reversal candidate if confirmed |
| Zigzag | 5-3-5 correction | B <= 61.8% A, C beyond A, channel shape | C=A / 161.8 targets are better than generic amplitude |
| Flat | 3-3-5 correction | B retrace, C limits, moving/failure variants | Current best trading class, but variants need separate tests |
| Triangle | 3-3-3-3-3 correction | b-d line, segment restrictions, thrust | Usually WAIT until thrust confirms; not a direct fade signal |
| X-wave | Connector between corrections | Complexity and size relative to prior correction | Current `double_corr` needs true x-wave filters |
| Double/triple zigzag | Complex correction | x-waves, channels, compaction | Can imitate impulse; needs channel and compaction tests |
| Combination/double three | Complex correction | x-waves, flat/triangle constraints | Should become context/scoring before direct trading |
| Multiwave | Segmented internal structure | Degree, complexity, extension | Required for HTF/LTF consistency |
| Missing wave | Ambiguous structure repair | Reverse logic, minimum data points | If multiple valid interpretations exist, confidence should drop |
| Energy rating | Expected retrace after compact correction | Same-degree next wave | Better TP/invalidations than fixed amplitude |
| Channeling | Geometric confirmation/discriminator | Impulse, zigzag, triangle, flat, terminal | High-priority A/B filter for entries |
| Time projection | Duration constraints | Same-degree waves and post-pattern speed | Use to mark stale/late signals and time targets |

## Current Implementation Coverage

| Layer | Existing implementation | Gap |
|---|---|---|
| Monowaves | `python/ewb/monowaves.py`; Pine zigzag state | Good baseline, but sensitivity and confirmation lag need per-TF calibration |
| Rule Determiner | `python/ewb/rules.py`; Pine `classifyRule`, `classifyCond`, `ruleToStructure` | Mostly diagnostic; not central to Action now |
| Similarity | `Pivot.similar_to_prev`; Pine `showSim` | Used visually, not enough for recursive degree grouping |
| Figure detection | `python/ewb/figures.py`; Pine `showFig` | Greedy/partial; not full cycle of grouping -> compaction -> reassessment |
| Pattern confirmation | `python/ewb/confirm.py`; Pine `confirmImpulse/Flat/Triangle` | Basic geometry only; formal/post-pattern checks missing from trade gating |
| Channels | Pine `drawImpulseChannels`, touchpoint helpers | Mostly visual; should become tested filters |
| Energy/time | Pine `drawEnergy`, `checkTimeEquality` | Not connected to targets, stale logic, or probabilities |
| HTF | `python/ewb/htf.py`; Pine HTF bias and active HTF wave | Bias uses last HTF pivots, not full higher-degree structural context |
| Trading | `flat`/`double_corr` fade with calibrated probability | Useful v0, but it bypasses several book-required validation layers |

## What Was Likely Hidden or Underused

1. Position indicators are the biggest missing guardrail. The rule that waves 2, 4, b, d, e, and x cannot be impulses should filter many false impulse/triangle contexts.
2. Compaction is not just drawing fewer labels. It changes the degree and forces reassessment. Without recursive compaction, MTF labels can drift.
3. Zigzag vs impulse ambiguity must be resolved before trading a 5-3-5 structure. A detected zigzag may be the tail of a larger impulse.
4. Post-pattern logic should drive targets and invalidations. Examples: terminal impulse must retrace to start quickly; moving correction should be followed by a strong impulse; failed C should reach the pattern start.
5. Channeling should be a signal quality layer. 0-2, 2-4, b-d and parallel-channel behavior are book-level confirmations.
6. Energy rating should replace part of the generic amplitude target logic for compact corrections.
7. Time projection should mark late/stale signals and expected completion windows, not just price levels.
8. X-wave complexity is required before treating `double_corr` as a high-confidence setup.
9. Intraday lessons are promising for practical entries, but most are draft/review and should not become mandatory rules before tests.

## Recommended Architecture From Books

```text
OHLC
  -> confirmed monowaves
  -> Rule 1-7 + condition a-f per monowave
  -> structural candidate list
  -> position indicator assignment
  -> same-degree grouping of 3/5 waves
  -> structural series match
  -> pattern rules
  -> compaction and reassessment
  -> channel/formal/post-pattern checks
  -> energy/time/Fibonacci targets
  -> HTF degree alignment
  -> Action now + levels + visual explanation
```

The Pine indicator should display the final state, but Python should remain the research source of truth until every added rule has historical evidence.

## Historical Test Plan

Use stocks top20/top100 and timeframes `15m`, `30m`, `1h`, `4h`, `1d`, `1w`.

| Test block | Purpose | Compare against |
|---|---|---|
| Baseline current `flat/double_corr` | Preserve current known behavior | Existing historical grid |
| `+position_valid` | Reject illegal impulse roles and center-wave false signals | Baseline winrate/EV/trade count |
| `+same_degree_compaction` | Use grouped/compacted figures, not raw pivots | Baseline and `+position_valid` |
| `+zigzag_vs_impulse_priority` | Stop misclassifying impulse tail as zigzag | Zigzag/impulse false-positive rate |
| `+channel_confirm` | Require 0-2/2-4/b-d/channel behavior | Winrate, EV, sample loss |
| `+post_pattern_targets` | Use book-derived target/invalidation logic | TP hit, SL hit, time exit |
| `+energy_target` | Replace/adjust full-amplitude targets | R multiple, TP rate, EV |
| `+time_projection` | Mark late/stale by expected duration | Late-entry loss reduction |
| `+HTF_degree_alignment` | Align current wave with higher-degree structure | OOS stability by TF |
| Intraday research filters | Test S-curve, VAL, Stella, ellipses, PTV | Research-only; no Pine gating yet |

Required metrics:

- winrate;
- EV after fees/slippage;
- profit factor;
- max drawdown;
- TP/SL/time-exit rate;
- trade count and sample stability;
- in-sample vs out-of-sample split;
- by ticker, sector, TF, long/short;
- signal freshness and confirmation lag;
- percentage of signals rejected by each book rule.

## Decision for Anton

Anton can use `Elliott Wave Brain - Monowaves MTF` today as a visual/trading assistant for confirmed `flat/double_corr` setups, with active current/HTF wave context. But it should not be presented as a full Neely engine yet.

The next correct milestone is not more cosmetic Pine overlays. It is a Python `Neely Core` research pass that produces, for each signal:

- current monowave;
- current structural label;
- current position inside parent pattern;
- compacted parent figure;
- HTF parent context;
- channel confirmation state;
- post-pattern expectation;
- book-derived entry, invalidation, target, and time window;
- final `BUY/SELL/WAIT` reason.

Only filters that improve out-of-sample winrate/EV without destroying sample size should be moved into Pine.
