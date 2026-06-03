# Elliott Wave Brain — инструкции для Claude Code

## Стек
Python 3.12, MarkItDown, Anthropic API (claude-opus-4-6), PyYAML

## Структура проекта
```
schemas/          ← схемы данных (НЕ ИЗМЕНЯТЬ без явного запроса)
aku/golden/       ← эталонные AKU (НЕ ИЗМЕНЯТЬ)
aku/{book_id}/    ← извлечённые AKU по книгам
tools/            ← pipeline инструменты
tools/_lib/       ← shared библиотека
inbox/            ← файлы книг для обработки
extracted/        ← результаты MarkItDown
brain-output/     ← финальные артефакты (KB + Spec)
docs/             ← протоколы и реестры
```

## Правила разработки
1. `schemas/` не изменять без явного запроса
2. `aku/golden/` не изменять — это эталон для промптов
3. AKU ID генерировать только через `python tools/aku_id_next.py`
4. После создания/изменения AKU — запускать `python tools/validate_aku.py`
5. `ANTHROPIC_API_KEY` только из `.env`, никогда в коде
6. Все пути через `tools/_lib/config.py` — не хардкодить

## Anti-hallucination (КРИТИЧНО)
- Один тип AKU за проход (definitions / mandatory_rules / conditional_rules / heuristics / exceptions)
- Максимум 10 AKU за запрос к Claude API
- `verbatim_quote` обязательна для каждого AKU
- Формализация — ОТДЕЛЬНЫЙ проход ПОСЛЕ верификации человеком
- При сомнении в трактовке → `requires_review: true`

## Порядок обработки глав Нили
1. Гл.2 — Моноволны (уровень 1)
2. Гл.3 — Предварительный анализ (уровень 2)
3. Гл.5 — Импульсные паттерны (уровень 4)
4. Гл.6 — Корректирующие паттерны (уровень 4)
5. Гл.4 — Группировка (уровень 3)
6. Гл.7 — Степени волн
7. Гл.8-12 — Продвинутые разделы

## Конечная цель
Из verified+formalized AKU → `brain-output/indicator-spec/spec_vN.json`
→ Pine Script индикатор для TradingView с MTF-синхронизацией волн.
