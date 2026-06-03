# ============================================================
# CONFLICT RESOLUTION POLICY v1.0
# Elliott Wave Brain
# ============================================================
#
# Принимается один раз. Изменения требуют явного решения (не молчаливого).
# Цель: устранить двусмысленность ДО того как она проявится в индикаторе.
# ============================================================

## Принцип 1 — Иерархия источников

Порядок приоритета при конфликте (от высшего к низшему):

1. **Neely (NeoWave)** — primary для всех mandatory/conditional rules
2. **Williams** — primary для trading_application heuristics
3. Будущие источники — по договорённости при добавлении

Иерархия применяется ТОЛЬКО к mandatory/conditional rules.
Для heuristics — каждый источник сохраняет свою версию отдельным AKU.

---

## Принцип 2 — Типы конфликтов и решения

### Тип A: Правило есть у одного, отсутствует у другого
```
Neely: mandatory rule X
Williams: не упоминает X
→ Создать один AKU, scope: neely-mwe-1990
   НЕ экстраполировать на Williams
```

### Тип B: Разные формулировки, одинаковый смысл
```
Neely: "Волна 4 не может перекрывать ценовой диапазон Волны 1"
Williams: "4-я волна не заходит в зону 1-й волны"
→ Один AKU, statement из Neely (priority=1)
   aliases: [формулировка Williams]
   source: оба источника через cross_refs
```

### Тип C: Одно и то же правило, разная сила
```
Neely: mandatory
Williams: heuristic (или наоборот)
→ Два отдельных AKU
   AKU-XXXX: strength=mandatory, scope: neely-mwe-1990
   AKU-YYYY: strength=heuristic, scope: williams-tc-1995
   contradicts_aku: [ссылка друг на друга]
   Запись в conflicts.yaml
```

### Тип D: Прямое противоречие (разные правила)
```
Neely: "X верно"
Williams: "X неверно" (или "должно быть Y")
→ Два AKU оба с strength=controversial
   Запись в conflicts.yaml с полем resolution:
     decision: neely | williams | unresolved
     rationale: обоснование решения
     affects_indicator: true | false
```

### Тип E: Терминологический конфликт
```
Neely называет: "Terminal Impulse"
Williams называет: "Ending Diagonal"
→ canonical_name берётся из источника с priority=1 (Neely)
   Версия Williams идёт в aliases[]
   Оба термина ищутся при поиске
```

---

## Принцип 3 — Регистр конфликтов

Каждый конфликт типа C и D ОБЯЗАТЕЛЬНО регистрируется в:
`docs/conflicts.yaml`

```yaml
# conflicts.yaml template
- conflict_id: CONF-001
  type: C                          # A|B|C|D|E
  topic: wave-degree
  description: "Краткое описание конфликта"
  sources_involved: [neely-mwe-1990, williams-tc-1995]
  aku_involved: [AKU-0042, AKU-0043]
  resolution:
    status: resolved               # resolved | unresolved | deferred
    decision: neely-mwe-1990       # чья версия принята, или null
    rationale: "Причина выбора"
    affects_indicator: true
  logged_at: 2026-06-02
```

---

## Принцип 4 — Что НЕ является конфликтом

Следующее НЕ регистрируется как конфликт:

- Разный уровень детализации (один автор подробнее другого)
- Дополнительные топики у одного автора (Williams добавляет Alligator — это не конфликт с Neely)
- Разные примеры для одного и того же правила
- Педагогические различия (один объясняет через пример, другой через определение)

---

## Принцип 5 — Для индикатора

Индикатор использует ТОЛЬКО:
- AKU с strength=mandatory ИЛИ strength=conditional
- AKU с status=verified
- AKU у которых formalization.status=verified
- В случае конфликта типа C/D: только версия с decision=neely-mwe-1990 (priority=1)

Индикатор НЕ использует:
- heuristic AKU (только для LLM-анализа)
- controversial AKU (до разрешения конфликта)
- draft или disputed AKU
