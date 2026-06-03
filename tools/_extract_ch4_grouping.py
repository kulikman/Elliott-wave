#!/usr/bin/env python3
"""Извлечение Гл.4 (группировка, Структурные Серии), in-session OCR Claude. status=draft."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from tools._lib.aku_io import save_aku, next_aku_id, now_iso, aku_path

AKUS = [
    # Структурные Серии A-E (шаблоны фигур)
    dict(type="pattern", strength="mandatory", topic="impulse", subtopics=["structural-series","structural-labels"],
        statement_ru="Структурная Серия Импульса (Стандартная фигура A): последовательность структурных обозначений :5 -:F3 -:?5 -:F3 -:L5.",
        quote="A. :5-:F3-:?5-:F3-:L5 — Импульс (трендовая волна)",
        page="4-2", section="Структурные Серии (Таблица 4-3)",
        aw="matching a 5-segment group to impulse template",
        cons="structural_series == [':5', ':F3', ':?5', ':F3', ':L5']", notes="'?' = любой Индикатор положения."),
    dict(type="pattern", strength="mandatory", topic="zigzag", subtopics=["structural-series","structural-labels"],
        statement_ru="Структурная Серия Зигзага (Стандартная фигура B): последовательность :5 -:F3 -:?5 (структура 5-3-5).",
        quote="B. :5-:F3-:?5 — Зигзаг (коррективная волна)",
        page="4-2", section="Структурные Серии (Таблица 4-3)",
        aw="matching a 3-segment group to zigzag template",
        cons="structural_series == [':5', ':F3', ':?5']", notes="Зигзаг = коррекция 5-3-5."),
    dict(type="pattern", strength="mandatory", topic="flat", subtopics=["structural-series","structural-labels"],
        statement_ru="Структурная Серия Плоской (Стандартная фигура C): последовательность :F3 -:c3 -:?5 (структура 3-3-5).",
        quote="C. :F3-:c3-:?5 — Плоская (коррективная волна)",
        page="4-2", section="Структурные Серии (Таблица 4-3)",
        aw="matching a 3-segment group to flat template",
        cons="structural_series == [':F3', ':c3', ':?5']", notes="Плоская = коррекция 3-3-5."),
    dict(type="pattern", strength="mandatory", topic="triangle", subtopics=["structural-series","structural-labels"],
        statement_ru="Структурная Серия Треугольника (Стандартная фигура D): последовательность :F3 -:c3 -:c3 -:?3 -:?3 (структура 3-3-3-3-3).",
        quote="D. :F3-:c3-:c3-:?3-:?3 — Треугольник (коррективная волна)",
        page="4-2", section="Структурные Серии (Таблица 4-3)",
        aw="matching a 5-segment group to triangle template",
        cons="structural_series == [':F3', ':c3', ':c3', ':?3', ':?3']", notes="Треугольник = 3-3-3-3-3."),
    dict(type="pattern", strength="mandatory", topic="ending-diagonal", subtopics=["structural-series","structural-labels"],
        statement_ru="Структурная Серия Терминала (Стандартная фигура E): последовательность :F3 -:c3 -:c3 -:?3 -:L3 (завершающая фигура).",
        quote="E. :F3-:c3-:c3-:?3-:L3 — Терминал (завершающая волна)",
        page="4-2", section="Структурные Серии (Таблица 4-3)",
        aw="matching a 5-segment group to terminal template",
        cons="structural_series == [':F3', ':c3', ':c3', ':?3', ':L3']", notes="Терминал (конечный диагональный треугольник)."),
    # Группировка
    dict(type="rule", strength="mandatory", topic="grouping-procedure", subtopics=["monowave","polywave"],
        statement_ru="При группировке выбираются только обособленные группы из 3 или 5 моноволн — лишь они могут сформировать стандартную поливолну. В первую очередь анализируются группы с наименьшей общей длиной и длительностью.",
        quote="Среди обособленных групп всегда выбирайте содержащие только 3 или 5 моноволн — они могут сформировать стандартную поливолну ... в первую очередь анализируйте группы волн с наименьшей общей длиной и длительностью.",
        page="4-3", section="Группы моноволн",
        aw="selecting a monowave group for grouping into a polywave",
        cons="monowave_count(group) in {3, 5} ; analyze smallest (length+duration) first", notes=None),
    dict(type="rule", strength="mandatory", topic="compaction", subtopics=["structural-series","structural-labels"],
        statement_ru="Если последнее структурное обозначение Стандартной Коррективной Серии не содержит Индикатор положения «L», эту Серию необходимо сжать в тройку (:3) и рассматривать как часть одной из Нестандартных фигур.",
        quote="Если последнее Структурное обозначение Стандартной Коррективной Серии не содержит Индикатор положения «L», эту Серию необходимо сжать в «тройку» (:3) и рассматривать как часть одной из Нестандартных ценовых фигур.",
        page="4-2", section="Структурные Серии (Таблица 4-3)",
        aw="standard corrective series whose last label lacks 'L' position indicator",
        cons="compact(series) -> ':3' ; treat as part of nonstandard figure", notes=None),
    # Зигзаг или Импульс
    dict(type="rule", strength="mandatory", topic="wave-identification", subtopics=["impulse","zigzag","multiple-interpretation"],
        statement_ru="«Зигзаг или Импульс?»: обнаружив :L5, завершающую предполагаемый Зигзаг, всегда сначала проверяй гипотезу Импульса — Зигзаг (:5-:F3-:L5) может быть тремя последними сегментами Импульса. Только если импульсная гипотеза нарушает Правила построения, принимается Зигзаг.",
        quote="Работая с Зигзагами, всегда обращайте внимание на два предшествующих им Структурных обозначения, чтобы убедиться, что случайно не пропустили Импульс. ... всегда проверяйте импульсную гипотезу ... прежде чем идентифицировать группу волн в качестве Зигзага. Если Импульсная ценовая фигура удовлетворяет всем Правилам построения, остановитесь на этом варианте.",
        page="4-8", section="Зигзаг или Импульс?",
        aw="a :L5 completes a candidate zigzag with 2 preceding labels",
        cons="test impulse_hypothesis FIRST; accept zigzag only if impulse violates construction rules", notes=None),
]

n = int(next_aku_id().split("-")[1])
saved = 0
for d in AKUS:
    aku_id = f"AKU-{n:04d}"
    aku = {
        "id": aku_id, "type": d["type"], "strength": d["strength"], "status": "draft",
        "topic": d["topic"], "subtopics": d["subtopics"],
        "statement_ru": d["statement_ru"], "statement_en": None,
        "source": {"book_id": "neely-mwe-1990", "page": d["page"],
                   "chapter": "Глава 4: Дальнейшие аналитические построения", "section": d["section"],
                   "figure_id": None, "verbatim_quote": {"text": d["quote"], "language": "ru"}},
        "formalization": {"status": "draft", "applies_when": d["aw"],
                          "constraint": d["cons"], "formalization_notes": d["notes"]},
        "aliases": [], "related_aku": ["AKU-0003"] if d["topic"]=="grouping-procedure" else [],
        "contradicts_aku": [], "extends_aku": None, "supersedes_aku": None,
        "created_by": "claude", "created_at": now_iso(),
        "review_notes": "Извлечено Claude через прямое чтение PDF (Гл.4, группировка/Структурные Серии). Полный текст — ch04-grouping.md.",
        "requires_review": True,
    }
    save_aku(aku, aku_path("neely-mwe-1990", 4, "dalnejshie-postroenia", aku_id))
    saved += 1; n += 1
print(f"Создано AKU (Гл.4 группировка): {saved}")
