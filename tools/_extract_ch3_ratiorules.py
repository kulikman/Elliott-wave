#!/usr/bin/env python3
"""Извлечение Правил соотношений длин Гл.3 (in-session OCR Claude). status=draft, формализация=draft."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from tools._lib.aku_io import save_aku, next_aku_id, now_iso, aku_path

AKUS = [
    dict(
        type="rule", strength="mandatory", topic="length-ratio-rules",
        subtopics=["monowave", "structural-labels"],
        statement_ru="Определитель Правил: применяемое к моноволне m1 Правило (1–7) определяется соотношением длины следующей моноволны m2 к m1: <38.2%→Пр.1; 38.2–61.8%→Пр.2; =61.8%→Пр.3; 61.8–100%→Пр.4; 100–161.8%→Пр.5; 161.8–261.8%→Пр.6; >261.8%→Пр.7.",
        quote="Если отношение m2 к m1: меньше 38,2%, см. Правило 1; от 38,2% включительно до 61,8% (не включая), см. Правило 2; ровно 61,8%, см. Правило 3; между 61,8% и 100% (не включая), см. Правило 4; от 100% включительно до 161,8% (не включая), см. Правило 5; между 161,8% и 261,8% (включительно), см. Правило 6; более 261,8%, см. Правило 7.",
        page="3-22", section="Правила соотношений длин волн / Определитель Правил",
        applies_when="classifying monowave m1 by retracement ratio",
        constraint="rule = 1 if ratio(m2,m1) < 0.382 else 2 if ratio(m2,m1) < 0.618 else 3 if ratio(m2,m1) == 0.618 else 4 if ratio(m2,m1) < 1.000 else 5 if ratio(m2,m1) < 1.618 else 6 if ratio(m2,m1) <= 2.618 else 7",
        notes="ratio(m2,m1) = вертикальная ценовая проекция m2 / проекция m1. Не зависит от направления m1.",
    ),
    dict(
        type="rule", strength="mandatory", topic="conditions-categories",
        subtopics=["length-ratio-rules"],
        statement_ru="Условие Правила (буква a–f) определяется соотношением длины предшествующей моноволны m0 к m1. Пороги Фибоначчи (38.2/61.8/100/161.8/261.8%) делят диапазон m0/m1 на условия; набор букв зависит от номера Правила (Пр.1: a–d, Пр.2: a–e, Пр.3: a–f, Пр.4: a–e, Пр.5–7: a–d).",
        quote="Соотношение m0/m1 определяет применение обозначенного буквой Условия этого Правила. ... В подзаголовке \"Условия\" каждого конкретного Правила ищите нужное вам соотношение m0/m1 (арабские цифры).",
        page="3-22", section="Правила соотношений длин волн / Условия",
        applies_when="refining a length-ratio Rule by ratio(m0, m1)",
        constraint="condition_letter = lookup(rule_number, ratio(m0,m1)) using Fibonacci breakpoints [0.382, 0.618, 1.000, 1.618, 2.618]",
        notes="Точное соответствие буква↔диапазон зависит от Правила; полная таблица в ch03-length-ratio-rules.md.",
    ),
    dict(
        type="rule", strength="conditional", topic="conditions-categories",
        subtopics=["length-ratio-rules"],
        statement_ru="Категория Условия (i/ii/iii) применяется при Правиле 4 и определяется соотношением m3/m2: 100–161.8%→i; 161.8–261.8%→ii; >261.8%→iii.",
        quote="Категория i: если длина m3 не меньше 100%, но меньше 161,8% длины m2; Категория ii: если длина m3 лежит в пределах 161,8–261,8% длины m2 (включительно); Категория iii: если длина m3 больше 261,8% длины m2.",
        page="3-26", section="Правила соотношений длин волн / Категории Правила 4",
        applies_when="rule == 4 (refining condition by ratio(m3, m2))",
        constraint="category = 'i' if 1.000 <= ratio(m3,m2) < 1.618 else 'ii' if ratio(m3,m2) <= 2.618 else 'iii'",
        notes=None,
    ),
    dict(
        type="rule", strength="mandatory", topic="length-ratio-rules",
        subtopics=["monowave"],
        statement_ru="Соотношение m2/m1 = 61.8% (Правило 3) указывает непосредственно на границу между Импульсами и Коррекциями — это наиболее трудный для определения структуры m1 случай, требующий измерения m0/m1 для уточнения.",
        quote="При точном равенстве длины m2 61,8% длины m1 применяется Правило 3. В этом случае структуру m1 труднее всего определить, так как соотношение 61,8% указывает непосредственно на границу между Импульсами и Коррекциями.",
        page="3-25", section="Правила соотношений длин волн / Правило 3",
        applies_when="ratio(m2, m1) == 0.618",
        constraint="structure(m1) is ambiguous (boundary :3/:5) -> resolve via ratio(m0, m1) condition",
        notes=None,
    ),
]

n = int(next_aku_id().split("-")[1])
saved = 0
for d in AKUS:
    aku_id = f"AKU-{n:04d}"
    aku = {
        "id": aku_id, "type": d["type"], "strength": d["strength"], "status": "draft",
        "topic": d["topic"], "subtopics": d["subtopics"],
        "statement_ru": d["statement_ru"], "statement_en": None,
        "source": {
            "book_id": "neely-mwe-1990", "page": d["page"],
            "chapter": "Глава 3: Предварительный анализ", "section": d["section"],
            "figure_id": None,
            "verbatim_quote": {"text": d["quote"], "language": "ru"},
        },
        "formalization": {"status": "draft", "applies_when": d["applies_when"],
                          "constraint": d["constraint"], "formalization_notes": d["notes"]},
        "aliases": [], "related_aku": [], "contradicts_aku": [],
        "extends_aku": None, "supersedes_aku": None,
        "created_by": "claude", "created_at": now_iso(),
        "review_notes": "Извлечено Claude через прямое чтение PDF (Гл.3, Правила соотношений длин). Полная таблица условий — в ch03-length-ratio-rules.md.",
        "requires_review": True,
    }
    save_aku(aku, aku_path("neely-mwe-1990", 3, "predvaritelnyj-analiz", aku_id))
    saved += 1
    n += 1
print(f"Создано AKU (Гл.3 Правила соотношений длин): {saved}")
