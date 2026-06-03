#!/usr/bin/env python3
"""Гл.8 стр.8-19..8-30: Чередование (сложность/строение) + Растянутые + Начальная точка. draft."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from tools._lib.aku_io import save_aku, next_aku_id, now_iso, aku_path

AKUS = [
    dict(type="rule", strength="mandatory", topic="rule-of-alternation",
        subtopics=["impulse","multiwave","complexity-rule"],
        statement_ru="Чередование по сложности (Intricacy): всегда предпочтительнее, чтобы одна из двух смежных волн была сегментированной (поливолна), а другая — нет. Волна 1 не может сегментировать в отсутствие сегментированной волны 2 (если рынок не формирует Терминальную фигуру).",
        quote="В отличие от коррективной фазы, волна 1 не может сегментировать в отсутствие сегментированной волны 2 (если рынок не формирует Терминальную фигуру). Чередование сложности волн 3 и 4 может наблюдаться таким же образом, как и между волнами 1 и 2.",
        page="8-19", section="Подробнее о Чередовании / Сложность",
        aw="impulse hypothesis, checking wave 1 segmentation",
        cons="is_segmented(wave_1) IMPLIES is_segmented(wave_2) OR is_terminal(impulse)",
        notes="Рис.8-15: типичные примеры сегментированных/несегментированных пар."),
    dict(type="rule", strength="mandatory", topic="rule-of-alternation",
        subtopics=["impulse","zigzag","flat","structural-series"],
        statement_ru="Чередование по строению (Construction): если смежные волны в Импульсной или Коррективной фигуре сегментируют, другие формы Чередования должны сохраняться для точности подсчёта. Зигзаг → следующая фигура того же Порядка будет Плоской или иной (не Зигзаг). Импульс (:5) → следующая всегда Коррекция (:3).",
        quote="Если смежные волны в Импульсной или Коррективной фигуре сегментируют, другие формы Чередования должны сохраняться, чтобы сохранить точность подсчёта. Одна из форм, в которой возможно Чередование [Сложности], является Конструкция волны. Если одна фигура Зигзаг, ожидается, что следующая фигура будет Зигзагом (см. Рисунок 8-16а). Если рынок формирует Импульсную фигуру, ожидаемое следующее движение того же Порядка всегда будет Коррективной фигурой.",
        page="8-20", section="Подробнее о Чередовании / Строение",
        aw="confirming alternation between adjacent figures",
        cons="if fig_A == 'zigzag': next_fig != 'zigzag' ; if fig_A == 'impulse': next_fig IS correction",
        notes="Рис.8-16a: Зигзаг ++ Плоская. Рис.8-16b: Импульс(:5) ++ Коррекция(:3)."),
    dict(type="rule", strength="mandatory", topic="rule-of-extension",
        subtopics=["impulse","multiwave"],
        statement_ru="Растянутость и многокомпонентность (сегментированность) — два независимых явления. Термин 'Растянутая' относится к самой длинной трендовой волне Импульса (1, 3 или 5). Самая распространённая ситуация: волна-3 Растянутая (xs3) + волна-5 сегментированная (s5). Менее вероятно: волна-1 Растянутая + волна-3 сегментированная. Наименее вероятно: волна-1 Растянутая + волна-5 сегментированная (скорее Терминал).",
        quote="Большинство эллиотовцев считают, что термин \"Растянутые волны\" характеризуется двумя неразрывными взаимосвязанными показателями: длиной и количеством сегментов в фигуре... Они могут применяться независимо друг от друга.",
        page="8-21", section="Подробнее о Растянутых волнах",
        aw="identifying extended wave in impulse",
        cons="extended_wave = longest(wave_1, wave_3, wave_5) ; most_probable: extended(wave_3) AND segmented(wave_5)",
        notes="Рис.8-17: xs3+s5 самый частый. Рис.8-18: xs3+s5 независимо (волна-3 растянута, волна-5 сегментирована)."),
    dict(type="rule", strength="mandatory", topic="rule-of-extension",
        subtopics=["impulse","fibonacci-ratios","price-projection"],
        statement_ru="Волна-5 Растянутая: длина волны-5, отсчитанная от конечной точки волны-3 (точка 'n'), обычно составляет 161.8% расстояния от начала волны-1 до конца волны-3 (точка 'm'). Волна-4 составляет 40-61.8% длины волны-3 и завершается Неудавшейся-с или Треугольником. После Растянутой пятой — откат 61.8-95% всей волны-5.",
        quote="Длина волны-5, отсчитанная от конечной точки волны-3 (\"n\" на рисунке), обычно составляет 161,8% расстояния от начала волны-1 до конца волны-3 (\"m\" на рисунке)... длина волны-4 составляет 40-61,8% длины волны-3... После Растянутой пятой следует быстрый откат на 61,8–95% длины всей волны-5.",
        page="8-26", section="Важно знать, какая из волн Импульса Растянутая / Волна-5 Растянутая",
        aw="wave_5 is extended (longest of 1,3,5)",
        cons="target_w5 = end(wave_3) + 1.618 * (end(wave_3) - start(wave_1)) ; retracement = 0.618..0.95 * length(wave_5)",
        notes="Рис.8-20 (продолжение): 'ложное пробитие' верхней линии тренда."),
    dict(type="rule", strength="mandatory", topic="wave-identification",
        subtopics=["impulse","foundations","analysis-workflow"],
        statement_ru="Большинство фигур Эллиота НЕ завершается в точке абсолютного максимума или минимума. 4 формы завершения без нового экстремума: A — Неудавшаяся пятая; B — Плоская с Неудавшейся c-волной; C — Сужающийся Неограничивающий Треугольник на вершине; D — Терминальная фигура. Начинать счёт следует от конца предыдущей фигуры, не от точки глобального экстремума.",
        quote="Верите вы в это или нет, но большинство фигур Эллиота не завершается в точке абсолютного максимума или минимума... Если начать анализ группы волн не с конечной точки фигуры Эллиота, прогнозы поведения рынка могут очень долго оставаться неверными.",
        page="8-27", section="Как выбирать начальную точку счёта",
        aw="choosing wave count start point",
        cons="start_point = end(previous_completed_figure) NOT = absolute_high_or_low ; look for secondary_spike AFTER global_extreme",
        notes="Рис.8-21: типичная ошибка новичка — старт от абсолютного экстремума. Рис.8-23: 4 формы завершения A/B/C/D."),
    dict(type="rule", strength="mandatory", topic="wave-identification",
        subtopics=["impulse","analysis-workflow"],
        statement_ru="Признаки неправильной начальной точки импульса: 1) длины волн 1, 3, 5 практически равны; 2) волны 2 и 4 не чередуются; 3) волна-2 нисходящего тренда длиннее предыдущей волны; 4) волна-2 пересекает линию тренда 0-2. Любой из этих признаков указывает на ошибку в выборе старта.",
        quote="В варианте А волнового счета обнаружены значительные логические ошибки... 1. Длины всех волн 1, 3 и 5 практически равны. 2. Волны 2 и 4 практически не чередуются. 3. Волна-2 нисходящего тренда больше волны (ii)... 4. Волна-2 пересекает линию тренда (0)-(ii).",
        page="8-29", section="Как выбирать начальную точку счёта / Рис.8-25",
        aw="validating impulse start point",
        cons="NOT(length(w1)≈length(w3)≈length(w5)) AND alternation(w2,w4) AND w2_not_cross_trendline_02",
        notes="Рис.8-25: Счёт A — ошибочный, Счёт B — правильный (Неограничивающий Треугольник + нисходящий импульс)."),
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
        "review_notes": "Извлечено Claude (PDF ч.2 Гл.8 стр.8-19..8-30, чередование/растяжение/начальная точка).",
        "requires_review": True,
    }
    save_aku(aku, aku_path("neely-mwe-1990", 8, "slozhnye-polimulti-makrovolny", aku_id))
    saved += 1; n += 1
print(f"Создано AKU (Гл.8 чередование+растяжение+старт): {saved}")
