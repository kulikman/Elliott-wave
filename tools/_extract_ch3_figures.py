#!/usr/bin/env python3
"""Извлечение процедур выделения фигур Гл.3 (3-60..3-69), in-session OCR Claude. status=draft."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from tools._lib.aku_io import save_aku, next_aku_id, now_iso, aku_path

AKUS = [
    dict(type="rule", strength="mandatory", topic="complexity-rule", subtopics=["grouping-procedure","wave-degree"],
        statement_ru="Уровни Сложности смежных (последовательно расположенных) ценовых фигур отличаются не более чем на единицу. Если уровни сложности соседних волн различаются более чем на 1 — группировка по методу Нили невозможна.",
        quote="Убедитесь, что Уровни Сложности смежных (последовательно расположенных) ценовых фигур ... отличаются не более чем на единицу. ... по методу Нили это было бы невозможно, если бы уровни сложности данных волн отличались более чем на единицу.",
        page="3-68", section="Особые условия",
        fstatus="draft", aw="grouping two adjacent waves/figures into a larger figure",
        cons="abs(complexity_level(fig_i) - complexity_level(fig_i+1)) <= 1",
        notes="Уровни сложности: 0=моноволна, 1=поливолна, 2=мультиволна, 3+=макроволна (Гл.7)."),

    dict(type="rule", strength="mandatory", topic="wave-identification", subtopics=["grouping-procedure"],
        statement_ru="Каждая конфигурация Эллиота состоит из нечётного количества волн. Между двумя граничными точками фигуры (волнами :L5/:L3) число волн должно быть нечётным; при чётном — поиск границы продолжается справа налево.",
        quote="Поскольку каждая конфигурация Эллиота должна состоять из нечетного количества волн, необходимо сосчитать число волн между двумя закрашенными кружками и, в случае его четности, продолжить поиск другой волны ... т. е. в обратном временном порядке.",
        page="3-66", section="Процедуры выделения ценовых фигур",
        fstatus="draft", aw="isolating an Elliott figure between two boundary waves",
        cons="wave_count(between boundary_waves) is odd AND >= 3",
        notes=None),

    dict(type="rule", strength="mandatory", topic="wave-identification", subtopics=["structural-labels"],
        statement_ru="Ценовая фигура Эллиота всегда завершается волной с обозначением :L5 или :L3. Для выделения фигур график просматривается слева направо в поиске первой волны :L5/:L3 — высока вероятность, что в этой точке завершается фигура Эллиота.",
        quote="Начиная с левого края графика, слева направо ищите первую волну с обозначением «:L5» и/или «:L3» ... поскольку высока вероятность, что в этой точке завершается ценовая фигура Эллиота. ... В любом случае ценовая фигура Эллиота должна завершаться волной «:L5» или «:L3», вне зависимости от наблюдаемого типа группировки.",
        page="3-64", section="Процедуры выделения ценовых фигур",
        fstatus="draft", aw="locating Elliott figure boundaries on the chart",
        cons="end_label(elliott_figure) in {':L5', ':L3'}",
        notes=None),

    dict(type="rule", strength="mandatory", topic="structural-labels", subtopics=["wave-identification","compaction"],
        statement_ru="Если компактная ценовая фигура пересекает свой собственный начальный уровень до завершения, её базовая Структура коррективна (:3) — вне зависимости от рекомендаций Неформальных правил логики.",
        quote="Если в процессе сведения ряда Структурных обозначений к одному символу обнаружена активность компактной ценовой фигуры, начальный уровень которой пересекается до ее завершения ... то базовая Структура такой компактной ценовой фигуры является коррективной по своему характеру («:3»), вне зависимости от рекомендаций Неформальных правил логики.",
        page="3-68", section="Особые условия",
        fstatus="draft", aw="compact figure crosses its own start_level before completion",
        cons="base_structure(figure) == ':3'",
        notes="Жёсткое правило, переопределяет Неформальные правила логики."),

    dict(type="definition", strength="mandatory", topic="structural-labels", subtopics=["impulse"],
        statement_ru="Структурное обозначение :5 (пятёрка) символизирует любую Импульсную волну, НЕ завершающую ценовую фигуру Эллиота — либо первую фазу Импульса/Зигзага, либо среднюю фазу Импульса/Сложной Коррекции.",
        quote="Это Структурное обозначение (пятерка) символизирует любую Импульсную волну, не завершающую ценовую фигуру Эллиота либо являющуюся первой фазой Импульса или Зигзага ЛИБО средней фазой Импульса или Сложной Коррекции.",
        page="3-64", section="Структурные обозначения / :5",
        fstatus="not_formalizable", aw=None, cons=None, notes=None),

    dict(type="definition", strength="mandatory", topic="structural-labels", subtopics=["channeling"],
        statement_ru="Структурное обозначение :L5 («последняя пятёрка») символизирует Импульс, завершающий более крупную ценовую фигуру Эллиота (возможно несколько сразу). Минимальное подтверждение — пересечение трендовой линии по конечным точкам m0 и m(-2) за время, не превышающее длительности формирования волны :L5.",
        quote="Поскольку волна с обозначением «:L5» всегда завершает более крупную ценовую фигуру Эллиота, она может одновременно завершать и несколько таких ценовых фигур. Минимальным требованием к ее подтверждению является пересечение линии тренда, проведенной по конечным точкам волн m0 и m(-2), которое должно произойти в течение периода времени, не превышающего длительности формирования волны с обозначением «:L5».",
        page="3-64", section="Структурные обозначения / :L5",
        fstatus="draft", aw="confirming a :L5 wave",
        cons="breaks(next_wave, trendline(end(m0), end(m-2))) AND duration(until_break) <= duration(L5_wave)",
        notes=None),
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
                   "chapter": "Глава 3: Предварительный анализ", "section": d["section"],
                   "figure_id": None, "verbatim_quote": {"text": d["quote"], "language": "ru"}},
        "formalization": {"status": d["fstatus"], "applies_when": d["aw"],
                          "constraint": d["cons"], "formalization_notes": d["notes"]},
        "aliases": [], "related_aku": [], "contradicts_aku": [],
        "extends_aku": None, "supersedes_aku": None,
        "created_by": "claude", "created_at": now_iso(),
        "review_notes": "Извлечено Claude через прямое чтение PDF (Гл.3, 3-60..3-69: выделение фигур, особые условия).",
        "requires_review": True,
    }
    save_aku(aku, aku_path("neely-mwe-1990", 3, "predvaritelnyj-analiz", aku_id))
    saved += 1; n += 1
print(f"Создано AKU (Гл.3 выделение фигур): {saved}")
