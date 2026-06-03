#!/usr/bin/env python3
"""Структурные списки Правил 4-7 (Неформальная логика), in-session OCR Claude. status=draft."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from tools._lib.aku_io import save_aku, next_aku_id, now_iso, aku_path

AKUS = [
    dict(topic="structural-labels", subtopics=["length-ratio-rules","monowave"],
        statement_ru="Правило 4 (61.8% < m2/m1 < 100%): структурные списки m1 по Условиям — a:{:F3,:c3,:s5,[:sL3]}, b:{:F3,:c3,:s5,(:sL3),(x:c3),[:L5]}, c:{:c3,(:F3),(x:c3)}, d:{:F3,(:c3),(x:c3)}, e:{:F3,(x:c3),[:c3]}. Вероятная метка :F3 (или :c3 при Условии c).",
        quote="Условие \"a\" {:F3/:c3/:s5/[:sL3]} ... Условие \"b\" {:F3/:c3/:s5/(:sL3)/(x:c3)/[:L5]} ... Условие \"c\" {:c3/(:F3)/(x:c3)} ... Условие \"d\" {:F3/(:c3)/(x:c3)} ... Условие \"e\" {:F3/(x:c3)[:c3]}",
        page="3-44", aw="rule(m1) == 4",
        cons="structure(m1) in {':F3',':c3',':s5',':sL3','x:c3',':L5'} ; primary := ':F3'",
        notes="Списки зависят от Условия a-e; см. ch03-informal-logic.md."),
    dict(topic="structural-labels", subtopics=["length-ratio-rules","monowave"],
        statement_ru="Правило 5 (100% ≤ m2/m1 < 161.8%): структурный список m1 = {:F3, :c3, :5, :L5, (:L3)}. Вероятная метка :F3.",
        quote="Правило 5 {:F3/:c3/:5/:L5/(:L3)}",
        page="3-51", aw="rule(m1) == 5",
        cons="structure(m1) in {':F3',':c3',':5',':L5','(:L3)'} ; primary := ':F3'",
        notes=None),
    dict(topic="structural-labels", subtopics=["length-ratio-rules","position-indicators"],
        statement_ru="Правило 6 (161.8% ≤ m2/m1 ≤ 261.8%): возможна любая Структура m1. Если ни одно описание не подходит — определять метку через последовательности Индикаторов положения (стр. 3-61).",
        quote="Правило 6 {возможна любая Структура; если ни одно из описаний не подходит, смотрите раздел о последовательностях Индикаторов положения на стр. 3-61}",
        page="3-55", aw="rule(m1) == 6",
        cons="structure(m1) := any ; resolve via position_indicator_sequences",
        notes="Большой откат m1 → структура неоднозначна."),
    dict(topic="structural-labels", subtopics=["length-ratio-rules","position-indicators"],
        statement_ru="Правило 7 (m2/m1 > 261.8%): возможна любая Структура m1. Если ни одно описание не подходит — через Индикаторы положения (стр. 3-61). Условия favor :5/:s5, :L5, :L3, :F3.",
        quote="Правило 7 {возможна любая Структура, если ни одно из описаний не подходит, см. раздел о последовательностях Индикаторов положения на стр. 3-61}",
        page="3-57", aw="rule(m1) == 7",
        cons="structure(m1) := any ; resolve via position_indicator_sequences",
        notes="Очень большой откат m1."),
]

n = int(next_aku_id().split("-")[1]); saved = 0
for d in AKUS:
    aku_id = f"AKU-{n:04d}"
    aku = {
        "id": aku_id, "type": "rule", "strength": "conditional", "status": "draft",
        "topic": d["topic"], "subtopics": d["subtopics"],
        "statement_ru": d["statement_ru"], "statement_en": None,
        "source": {"book_id": "neely-mwe-1990", "page": d["page"],
                   "chapter": "Глава 3: Предварительный анализ",
                   "section": "Неформальные Правила логики / структурные списки",
                   "figure_id": None, "verbatim_quote": {"text": d["quote"], "language": "ru"}},
        "formalization": {"status": "draft", "applies_when": d["aw"],
                          "constraint": d["cons"], "formalization_notes": d["notes"]},
        "aliases": [], "related_aku": [], "contradicts_aku": [],
        "extends_aku": None, "supersedes_aku": None,
        "created_by": "claude", "created_at": now_iso(),
        "review_notes": "Извлечено Claude через прямое чтение PDF (Гл.3, структурные списки Правил 4-7).",
        "requires_review": True,
    }
    save_aku(aku, aku_path("neely-mwe-1990", 3, "predvaritelnyj-analiz", aku_id))
    saved += 1; n += 1
print(f"Создано AKU (структурные списки Правил 4-7): {saved}")
