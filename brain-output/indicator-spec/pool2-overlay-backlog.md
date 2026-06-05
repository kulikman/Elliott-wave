# Pool 2 Overlay Backlog

Практический backlog реализации `wave_books_pool_2` как research overlay поверх Neely Core. Этот документ не является исполнимым spec и не создаёт новые правила; он описывает порядок разработки после human review.

## Gate

- До human review не создавать `spec_vN.json` для pool 2.
- Сначала Python research prototype, затем Pine перенос.
- Pool 2 не меняет core-разметку `python/ewb/figures.py` и Pine Neely Core.
- Каждый будущий сигнал должен ссылаться на AKU и нести `requires_review`/`is_core_rule`.
- Trade management и PTV включаются только как отдельные режимы.

## Current Code Anchors

- Python core figures: `python/ewb/figures.py`
- Python confirmations: `python/ewb/confirm.py`
- Python research data/backtests: `python/ewb/research/`, `python/scripts/`
- Pine core MTF monowaves: `pine/ewb_monowaves_mtf.pine`
- Pine confirmations: `pine/ewb_confirm.pine`
- Current strict spec: `brain-output/indicator-spec/spec_v3.0.json`
- Pool 2 architecture: `brain-output/indicator-spec/pool2-overlay-architecture.md`

## Sprint P2-A — Review-Gated Signal Contract

Goal: define a small, stable object model for overlay signals.

Deliverables:

- `Pool2Signal` research dataclass in Python after review.
- JSON-like fields:
  - `module`
  - `signal`
  - `confidence`
  - `source_aku`
  - `depends_on_core`
  - `requires_review`
  - `is_core_rule`
  - `start_idx`
  - `end_idx`
  - `price_level`
  - `notes`

Acceptance:

- No effect on existing `Figure` matching.
- Unit tests cover serialization and required fields.
- Debug output can be joined to existing figure rows.

## Sprint P2-B — High-Confidence Structural Overlay

Goal: implement only review-accepted high-confidence candidates.

Initial modules:

- `P2-01 S-ка`: related to extended wave 3.
- `P2-02 Stella`: related to extended wave 5 / terminal.
- `P2-03 VAL`: related to extended wave 1 / terminal.
- `P2-05 Moving Correction`: related to moving/running flat.
- `P2-04 Ellipse`: only as zigzag/terminal frame, not as classifier override.

Acceptance:

- Signals are generated only when a Neely Core candidate already exists.
- Signals never change `Figure.type`, `confirmed`, or `checks`.
- All signals carry `is_core_rule: false`.
- Synthetic tests show no regressions in existing figure tests.

## Sprint P2-C — Visual Geometry Research

Goal: prototype geometry helpers for arcs, touches, and ellipses.

Research candidates:

- Third-touch detection on pivot arcs.
- S-curve envelope fit.
- Ellipse frame fit around 3- or 5-wave structures.
- Breakout-line retest detection.

Acceptance:

- Geometry helpers return candidates with low/medium/high confidence.
- False positives are measured on existing datasets.
- No trading output yet.
- Every visual geometry signal remains `requires_review: true` until validated.

## Sprint P2-D — Experimental PTV Mode

Goal: isolate PTV/π/√n calculations from core wave logic.

Inputs:

- User-selected anchors.
- Optional candidate pivots from Neely Core.
- Coefficient set: `sqrt2`, `sqrt3`, `sqrt5`, `pi`.

Outputs:

- PTV table.
- Projected price/time levels.
- Error percent against observed pivot, if available.

Acceptance:

- PTV code cannot affect core pattern validity.
- UI/outputs label it as `Experimental PTV`.
- Tests cover coefficient calculations and no-core-side-effects.

## Sprint P2-E — Trade Management Overlay

Goal: add advisory-only hints after pattern/setup signals are stable.

Candidates:

- Positive lock hints.
- 8-10 point stop hint.
- Breakeven hint.
- Add-position hint.
- News mode hint.

Acceptance:

- Disabled by default.
- Requires at least one upstream Pool 2 setup signal.
- No buy/sell automation.
- Clear separation from Neely Core validation.

## Sprint P2-F — Pine Research Overlay

Goal: port only stable, review-approved overlays to Pine.

Recommended Pine path:

- Keep `ewb_monowaves_mtf.pine` as Neely Core.
- Add a separate script first, for example `ewb_pool2_overlay.pine`.
- Later merge UI into one indicator only if Pine limits allow it.

Acceptance:

- Default overlay toggles are off.
- Debug labels can show AKU IDs.
- No change to existing Pine core behavior.
- Pine visual output matches Python research on a small fixture set.

## Priority Matrix

| Priority | Module | Reason |
| --- | --- | --- |
| P1 | S-ка / Стэлла / ВАЛ | Strongest bridge to extended impulses and terminal variants. |
| P1 | Moving Correction | Strongest bridge to existing moving/running flat logic. |
| P2 | Ellipse | Valuable, but geometry is visual and needs more review. |
| P3 | Third Touch | Useful as visual confirmation, but author-specific. |
| P4 | PTV | Potentially valuable, but experimental and not core Neely. |
| P5 | Positive Lock / Trade Management | Trading layer, should come last. |

## Stop Conditions

Pause implementation if:

- Human review rejects the high-confidence merge candidates.
- A candidate requires changing core figure classification.
- Vision-only geometry cannot be verified on examples.
- PTV is requested to influence Neely Core labels.

## Next Concrete Step After Review

Create a Python-only research module:

```text
python/ewb/pool2/
  __init__.py
  signals.py
  structural.py
  geometry.py
  ptv.py
```

Initial tests:

```text
python/tests/test_pool2_signals.py
python/tests/test_pool2_structural.py
```
