# Pool 2 Overlay Architecture

Стратегия: `wave_books_pool_2` развивается как отдельный overlay-модуль поверх Neely Core, а не как прямое расширение строгого ядра. Финальный пользовательский интерфейс может быть единым, но логика должна оставаться разделённой.

Главный продуктовый инвариант: overlay нужен не ради красивой разметки, а ради оценки вероятностей дальнейшего движения цены акции, чтобы Антон мог принимать решения о покупке или продаже.

## Decision

- `Neely Core`: verified/formalized правила Нили, structural series, grouping, degree, pattern validation, MTF synchronization.
- `Pool 2 Overlay`: авторские фигуры и торговые эвристики из внутридневных уроков.
- `Trade Management`: положительный замок, стопы, новости, БУ, доливки.
- `Experimental PTV`: PTV-треугольник, π, √2/√3/√5, формулы роста и погрешности.

Pool 2 не должен менять core-разметку. Он может только читать результаты core и рисовать/выдавать дополнительные гипотезы.

## Layer Model

```text
price data
  -> Neely Core
       -> monowaves
       -> structural labels
       -> candidate patterns
       -> degree / MTF context
       -> post-pattern expectations
  -> Pool 2 Overlay
       -> S-ка / Стэлла / ВАЛ visual candidates
       -> ellipse / third-touch candidates
       -> moving-correction trade setup candidates
       -> PTV/π projections
       -> positive-lock management hints
```

## Core Inputs Available To Pool 2

Pool 2 may consume:

- Current monowave/polywave pivots.
- Candidate Neely pattern type: impulse, terminal, zigzag, flat, triangle.
- Extended wave hint: extended 1 / 3 / 5.
- Running/moving flat candidate.
- Post-pattern expectation: retrace zone, start-level reach, line break confirmation.
- MTF degree context from Neely Core.

Pool 2 must not override:

- Verified wave label.
- Pattern validity.
- Degree assignment.
- Core MTF synchronization.

## Pool 2 Modules

### P2-01 S-ка Overlay

Purpose: detect/annotate S-curve candidates and relate them to possible impulse with extended wave 3.

Inputs:

- Neely impulse candidate.
- Extended wave 3 hint.
- Third-touch/arc geometry candidate.
- Retracement context: 50%, 100%, >100%.

Outputs:

- `s_curve_candidate`
- `s_curve_retrace_scenario`: `trend_continuation_50_or_less`, `flat_100`, `support_resistance_100_plus`, `trend_end_black_swan`
- `requires_review` until visual rules are manually verified.

### P2-02 Stella Overlay

Purpose: detect/annotate Stella candidates and relate them to possible impulse with extended wave 5 or terminal variant.

Inputs:

- Neely impulse candidate.
- Extended wave 5 hint.
- Terminal impulse candidate.
- Visual retracement candidates 61%, 81%, >81%.

Outputs:

- `stella_candidate`
- `stella_terminal_candidate`
- `stella_retrace_zone`

### P2-03 VAL Overlay

Purpose: detect/annotate VAL candidates and relate them to possible impulse with extended wave 1 or terminal variant.

Inputs:

- Neely impulse candidate.
- Extended wave 1 hint.
- Terminal impulse candidate.
- Third-touch arc candidate.

Outputs:

- `val_candidate`
- `val_terminal_candidate`
- `val_touch_count`: 2 or 3
- `val_retrace_warning`

### P2-04 Ellipse Overlay

Purpose: frame candidate wave structures with ellipses without changing core pattern classification.

Inputs:

- Zigzag candidate.
- Terminal candidate.
- Line-break confirmation.
- Support/resistance context.

Outputs:

- `ellipse_candidate`
- `ellipse_as_zigzag_frame`
- `ellipse_end_at_breakout_or_sr`
- `ellipse_terminal_variant`

### P2-05 Moving Correction Setup

Purpose: expose trade setup candidates around moving/running correction, based on already detected flat/moving correction candidates.

Inputs:

- Flat/running flat candidate from Neely Core.
- Post-pattern expectation.
- 161.8% follow-through candidate.
- `c >= 61.8% of a` candidate.

Outputs:

- `moving_correction_candidate`
- `trend_add_on_setup`
- `wave_c_entry_candidate`
- `breakout_line_entry_candidate`

### P2-06 PTV Experimental Projection

Purpose: calculate and display author-specific PTV/π/√n projections as experimental geometry.

Inputs:

- Price-time vector anchors.
- MTF degree context.
- User-selected coefficient set: `sqrt2`, `sqrt3`, `sqrt5`, `pi`.

Outputs:

- `ptv_triangle`
- `ptv_projection_price`
- `ptv_projection_time`
- `ptv_error_percent`

Hard rule: PTV signals are never core Neely rules until primary-source validation.

### P2-07 Trade Management Overlay

Purpose: display management hints only after a separate pattern/setup candidate exists.

Inputs:

- Pool 2 setup candidate.
- User risk settings.
- News mode toggle.

Outputs:

- `positive_lock_hint`
- `stop_8_10_points_hint`
- `breakeven_hint`
- `add_position_hint`

Hard rule: this layer is advisory and must be visually separated from wave validation.

## TradingView UI Modes

Recommended single-indicator UI with internal separation:

- `Neely Core`: strict wave logic.
- `Pool 2 Overlay`: S-ка, Стэлла, ВАЛ, ellipses, third touch.
- `Trade Management`: lock, stop, breakeven, add-ons.
- `Experimental PTV`: PTV and growth coefficients.
- `Debug / Review`: show AKU IDs and `requires_review` labels.

Default:

- `Neely Core`: on.
- `Pool 2 Overlay`: off until review.
- `Trade Management`: off.
- `Experimental PTV`: off.
- `Debug / Review`: on in research builds, off in user builds.

## Output Contract

Every Pool 2 signal should carry:

```json
{
  "module": "P2-01",
  "signal": "s_curve_candidate",
  "confidence": "low|medium|high",
  "source_aku": ["AKU-0248"],
  "depends_on_core": ["impulse-extension"],
  "requires_review": true,
  "is_core_rule": false
}
```

## Development Order

1. Keep Pool 2 docs and AKU separate until human review.
2. Build a non-trading research overlay from reviewed high-confidence candidates only.
3. Add medium-confidence candidates as debug-only visual marks.
4. Add PTV as experimental mode, with no core influence.
5. Add trade management hints last, after visual setup signals are stable.

## Merge Policy

Can become related to Neely Core after review:

- S-ка to extended wave 3.
- Стэлла to extended wave 5 / terminal.
- ВАЛ to extended wave 1 / terminal.
- Moving correction to running/moving flat.
- Ellipse to zigzag/terminal framing.

Must remain separate unless a primary source proves otherwise:

- Positive lock.
- PTV/π/√3 formulas.
- News scenarios.
- Stop placement and position management.
