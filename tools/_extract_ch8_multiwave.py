#!/usr/bin/env python3
"""Гл.8 PDF ч.2 стр.8-11..8-17: большая x-волна (Таблица B) + мультиволны. status=draft."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from tools._lib.aku_io import save_aku, next_aku_id, now_iso, aku_path

AKUS = [
    dict(type="pattern", strength="mandatory", topic="combination",
        subtopics=["x-wave","structural-series","flat","triangle"],
        statement_ru="Таблица B (большая x-волна): Двойная Тройка — (3-3-5) ++ x:3(большой) ++ (3-3-5). Сжимается в ':3'. Рис.8-10. Самая распространённая разновидность: обе тройки — Плоские.",
        quote="(3-3-5) + (х-волна) + (3-3-5) = Двойная Тройка = 3",
        page="8-11", section="Таблица B / Двойная Тройка",
        aw="two flat corrections separated by large x-wave (>= 61.8% of correction_1)",
        cons="series=[':3'(Flat), x_wave_large(':3'), ':3'(Flat)] ; compact → ':3'",
        notes="Рис.8-10: встречается редко. Рис.8-10 (продолжение): самая распространённая разновидность."),
    dict(type="pattern", strength="mandatory", topic="combination",
        subtopics=["x-wave","structural-series","flat","triangle"],
        statement_ru="Таблица B: Комбинация Двойная Тройка — (3-3-5) ++ x:3 ++ (3-3-3-3-3, Сужающийся Треугольник). Сжимается в ':3'. Рис.8-9.",
        quote="(3-3-5) + (х-волна) + (3-3-3-3-3, с.т.) = Комбинация Двойная Тройка = 3",
        page="8-11", section="Таблица B / Комбинация Двойная Тройка",
        aw="flat followed by large x-wave followed by contracting triangle",
        cons="series=[':3'(Flat), x_wave(':3'), ':3'(Triangle)] ; compact → ':3'",
        notes=None),
    dict(type="pattern", strength="mandatory", topic="combination",
        subtopics=["x-wave","structural-series","flat","triangle"],
        statement_ru="Таблица B: Тройная Тройка — (3-3-5) ++ x:3 ++ (3-3-5) ++ x:3 ++ (3-3-5). Очень редкая фигура. Сжимается в ':3'. Рис.8-12. Перемещается с трендом на один Порядок выше.",
        quote="(3-3-5) + (х-волна) + (3-3-5) + (х-волна) + (3-3-5) = Тройная Тройка = 3",
        page="8-11", section="Таблица B / Тройная Тройка",
        aw="three flat corrections separated by two large x-waves",
        cons="series=[':3',:3(x),':3',:3(x),':3'] ; compact → ':3' ; trend_drift == true",
        notes="Рис.8-12: крайне редка. Медленно перемещается с трендом."),
    dict(type="rule", strength="mandatory", topic="multiwave",
        subtopics=["impulse","complexity-rule","rule-of-extension"],
        statement_ru="Мультиволновый Импульс: одна и только одна из трёх нечётных волн (1, 3 или 5) должна быть поливолной (сегментированной). Две остальные нечётные волны должны быть моноволнами.",
        quote="Одна и только одна из трёх нечётных волн в Импульсной фигуре (волна 1, 3 или 5) должна быть поливолной. Две остальные должны быть моноволнами.",
        page="8-16", section="Формирование мультиволн / Импульсы",
        aw="classifying multiwave impulse",
        cons="count(polywave IN {wave_1, wave_3, wave_5}) == 1 AND monowave_count({wave_1,wave_3,wave_5} - polywave) == 2",
        notes=None),
    dict(type="rule", strength="mandatory", topic="multiwave",
        subtopics=["impulse","rule-of-alternation","complexity-rule"],
        statement_ru="Мультиволновый Импульс: как минимум одна коррективная фаза (волна 2 или 4) должна быть поливолной. Самая длинная Коррекция должна следовать непосредственно перед или после растянутой импульсной волны.",
        quote="Как минимум одна Коррекция (волна 2 или 4) Импульса должна быть поливолной... Самая длинная Коррекция (волна 2 или 4) Импульса должна следовать непосредственно перед или после растянутой волны.",
        page="8-16", section="Формирование мультиволн / Импульсы / Правила",
        aw="classifying multiwave impulse, identifying extended wave",
        cons="count(polywave IN {wave_2, wave_4}) >= 1 AND longest_correction IS adjacent_to extended_wave",
        notes=None),
    dict(type="rule", strength="mandatory", topic="multiwave",
        subtopics=["flat","zigzag","complexity-rule"],
        statement_ru="Мультиволновая Коррекция: одна или две пятёрки (':5') в более крупной фигуре должны быть явно сегментированы в поливолне. Если сегментирована только одна пятёрка — она должна быть c-волной Зигзага или Плоской. Очень высока вероятность, что b-волна мультиволны будет Коррективной поливолной.",
        quote="Одна или две пятерки (\":5\") в более крупной фигуре должны быть явно (визуально) сегментированы в поливолне... Очень высока вероятность, что b-волна мультиволны будет Коррективной поливолной.",
        page="8-17", section="Формирование мультиволн / Коррективы",
        aw="classifying multiwave correction",
        cons="count(polywave ':5') IN {1,2} AND if count==1: polywave(':5') IS c_wave AND polywave(b_wave) IS corrective",
        notes=None),
]

n = int(next_aku_id().split("-")[1]); saved = 0
for d in AKUS:
    aku_id = f"AKU-{n:04d}"
    aku = {
        "id": aku_id, "type": d["type"], "strength": d["strength"], "status": "draft",
        "topic": d["topic"], "subtopics": d["subtopics"],
        "statement_ru": d["statement_ru"], "statement_en": None,
        "source": {"book_id": "neely-mwe-1990", "page": d["page"],
                   "chapter": "Глава 8: Формирование сложных поли-, мульти- и макроволн",
                   "section": d["section"], "figure_id": None,
                   "verbatim_quote": {"text": d["quote"], "language": "ru"}},
        "formalization": {"status": "draft", "applies_when": d["aw"],
                          "constraint": d["cons"], "formalization_notes": d["notes"]},
        "aliases": [], "related_aku": [], "contradicts_aku": [],
        "extends_aku": None, "supersedes_aku": None,
        "created_by": "claude", "created_at": now_iso(),
        "review_notes": "Извлечено Claude (PDF ч.2 Гл.8 стр.8-11..8-17, Таблица B + мультиволны).",
        "requires_review": True,
    }
    save_aku(aku, aku_path("neely-mwe-1990", 8, "slozhnye-polimulti-makrovolny", aku_id))
    saved += 1; n += 1
print(f"Создано AKU (Гл.8 Таблица B + мультиволны): {saved}")
