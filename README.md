# Elliott Wave Brain

База знаний по волновому анализу → Индикатор-анализатор волн.

## Концепция

Из книг по волновому анализу извлекаются **Atomic Knowledge Units (AKU)** —
минимальные неделимые единицы знания (правило, определение, паттерн).
Из AKU генерируются два выхода:
- **LLM Knowledge Base** — markdown для аналитических чатов
- **Indicator Spec** — JSON-спека для алгоритма-индикатора

## Источники

| ID | Книга | Автор | Приоритет |
|----|-------|-------|-----------|
| neely-mwe-1990 | Mastering Elliott Wave | Glenn Neely | 1 (primary) |
| williams-tc-1995 | Trading Chaos | Bill Williams | 2 |

## Структура проекта

```
/schemas/          ← схемы данных (не менять без обоснования)
  aku.schema.yaml      — структура одного AKU
  taxonomy.yaml        — закрытый список топиков
  books.yaml           — реестр источников
  conflict-policy.md   — правила разрешения конфликтов

/aku/              ← все Atomic Knowledge Units
  /golden/             — 10 эталонных AKU (hand-crafted)
  /neely/              — AKU из книги Нили
    /ch02-monowave/
    /ch03-preliminary/
    ...
  /williams/           — AKU из книги Уильямса

/tools/            ← утилиты
  validate_aku.py      — валидатор
  aku_id_next.py       — генератор следующего ID

/docs/             ← документация
  extraction-protocol.md  — протокол работы с Claude
  conflicts.yaml          — реестр конфликтов между источниками
  taxonomy-changes.md     — история изменений taxonomy

/raw-vault/        ← оригинальные файлы (не редактировать)
  /neely-mwe-1990/
/extracted/        ← результаты MarkItDown
  /neely-mwe-1990/
/inbox/            ← сюда бросать файлы для обработки

/brain-output/     ← финальные артефакты
  /kb/                 — markdown база знаний
  /indicator-spec/     — JSON спека для индикатора
```

## Фазы проекта

| Фаза | Описание | Gate |
|------|----------|------|
| **0: Фундамент** | Схемы, golden AKU, validator | Validator зелёный на 10 golden AKU |
| **1: Пилот** | Одна глава (Нили Гл.2) end-to-end | 80%+ AKU не требуют правки |
| **2: Извлечение** | Все главы Нили, затем Уильямс | Все AKU верифицированы |
| **3: Канонизация** | Слияние, конфликты | Единая онтология без orphan refs |
| **4: Brain** | Vector index, генераторы | Semantic search работает |

**Текущая фаза: 0**

## Быстрый старт

```bash
# Установка зависимостей
pip install pyyaml

# Валидация всех AKU
python tools/validate_aku.py

# Следующий доступный ID
python tools/aku_id_next.py

# Валидация конкретной папки
python tools/validate_aku.py aku/golden/
```

## Создание нового AKU

1. Получи следующий ID: `python tools/aku_id_next.py`
2. Скопируй шаблон из `schemas/aku.schema.yaml`
3. Положи в `/aku/{book_id}/{chapter}/AKU-XXXX.yaml`
4. Заполни по протоколу: `docs/extraction-protocol.md`
5. Запусти валидатор: `python tools/validate_aku.py`

## Правила работы с базой

- **book_id никогда не менять** — ломает все AKU
- **taxonomy изменять только через docs/taxonomy-changes.md**
- **AKU не удалять** — только `status: deprecated` + `supersedes_aku`
- **Каждый конфликт** → запись в `docs/conflicts.yaml`
- **Формализация** — только после верификации содержания

## Anti-hallucination

Читай `docs/extraction-protocol.md` перед каждой сессией извлечения.
Ключевые правила:
- Один источник за раз
- Один тип AKU за проход (не смешивать definitions с rules)
- Максимум 10 AKU за один запрос Claude
- Цитата обязательна для verified
- Формализация — отдельный проход
