# Refactor Audit Baseline

Дата: 2026-06-04

## Проверки baseline

- `python3 -m pytest -q python/tests` должен проходить без warnings.
- `python3 -m compileall -q python tools` должен проходить.
- `python3 tools/validate_aku.py` должен показывать 247 прошедших AKU, 0 ошибок, 0 warnings.

## Подтвержденные факты

- Реальный интерпретатор в текущем окружении: Python 3.14.4 через `python3`.
- `python` в shell может отсутствовать, поэтому локальные команды проверки используют `python3`.
- `requirements.txt` должен покрывать оба слоя: AKU/tooling и research/backtest.
- Python core (`python/ewb`) не имеет обнаруженных циклических импортов.
- Pine matcher в `pine/ewb_monowaves_mtf.pine` пока расходится с Python hybrid matcher и требует отдельного parity-спринта.
- Research artifacts (`python/data/*.parquet`, `docs/validation/screenshots/**/*.png`) уже tracked в git; это repo policy вопрос, а не ошибка кода.

## Нельзя менять без отдельного подтверждения

- `schemas/`
- `aku/golden/`
- AKU-файлы, кроме явно запрошенного изменения
- `.env`, secrets, auth, billing/payment logic

## Нельзя ломать при рефакторинге

- `entry_idx = f.pivots[-1].confirmation_idx`
- HTF timing через `p.confirmation_idx`
- Финальная стратегия торгует только `flat` и `double_corr` fade
- Position sizing: `equity * 0.01 / amp_pct`, capped at 50% equity

## Требует ручной проверки

- `pine/ewb_confirm.pine`: `lookahead_on` допустим для ручного confirmer, но не для автоматических сигналов без отдельной проверки.
- Pine W5-related checks: часть проверок использует только `p0..p4`, поэтому нужно уточнить semantics перед исправлением.
- Потенциально мертвый код: `monowave_dirs`, `summary`, `confirmed_idx`, неиспользуемые imports в `figures.py`.

## Дальнейшие спринты

1. Baseline Hygiene: тесты, зависимости, конфигурация, audit baseline.
2. Research Shared Core: вынести universe/download/costs/strategy/portfolio без изменения поведения.
3. Backtest Hardening: убрать silent errors, добавить schema checks и regression fixtures.
4. Pine Parity Audit: описать расхождения Pine/Python на synthetic cases.
5. Pine Hybrid Matcher: перенести Python hybrid matcher в Pine.
