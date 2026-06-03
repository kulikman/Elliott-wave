#!/usr/bin/env python3
"""Гл.12 PDF ч.3: Каналы (уникальные применения) + Распознавание с помощью каналов. draft."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from tools._lib.aku_io import save_aku, next_aku_id, now_iso, aku_path

AKUS = [
    dict(type="rule", strength="mandatory", topic="channeling",
        subtopics=["impulse","analysis-workflow","wave-identification"],
        statement_ru="Волна-2: строить линию тренда 0-2 от точки '0' через нижнюю точку коррективного движения W2. Пока линия 0-2 не пробита → W2 ещё развивается и считается завершённой в точке касания линии тренда. Если линия пробита до завершения W3 (до уровня 61.8% W1) → W2 ещё продолжается.",
        quote="После того, как рынок развернулся в противоположном направлении (относительно волны-1) и снова развернулся вверх..., проведите линию от точки \"0\" через нижнюю точку понижательного движения, которое вы предположительно считаете волной-2... Пока линия тренда \"0-2\" не пробита, вы можете считать волну-2 завершенной, причем завершенной именно в точке, где она касается линии тренда.",
        page="12-1", section="Каналы / Волна-2",
        aw="confirming wave-2 completion using 0-2 trendline",
        cons="trendline_0_2 = line(start=p0, end=p2) ; wave_2_complete WHEN price touches trendline_0_2 ; wave_2_ongoing IF trendline_0_2 broken BEFORE wave_3 >= 0.618*wave_1",
        notes="Рис.12-1: Диаграммы A/B/C. Пока линия 0-2 не пробита В4→W2 завершена у линии."),
    dict(type="rule", strength="mandatory", topic="channeling",
        subtopics=["impulse","combination","x-wave"],
        statement_ru="Определение Подвижной Двойной Тройки во второй волне: ни одна часть волны-3 не должна пробивать настоящую линию тренда 0-2. Если после предполагаемой W2 следует коррективная фаза, пробивающая линию 0-2, и это повышение не было достаточно значительным для волны-3, то рынок находится в Подвижной Двойной Тройке. Признак: отсутствие Чередования между предполагаемыми W2 и W4.",
        quote="Согласно той же идее... ни одна часть волны-3 не должна пробивать настоящую линию тренда 0-2... Другая важная причина, почему эта фигура не может быть интерпретирована как волны 1, 2, 3, 4, за которыми должна последовать 5-я, – это недостаток Чередования между предполагаемыми 2-й и 4-й волнами.",
        page="12-2", section="Каналы / Определение Подвижной Двойной Тройки",
        aw="wave_3 breaks trendline_0_2",
        cons="wave_3 MUST NOT break trendline_0_2 ; if break AND no_alternation(w2, w4): figure IS moving_double_three",
        notes="Рис.12-2: ошибочная и правильная интерпретация."),
    dict(type="rule", strength="mandatory", topic="channeling",
        subtopics=["impulse","wave-identification","time-projection"],
        statement_ru="Реальная линия тренда 2-4 (подтверждение завершения W5): как только W5 завершена, рынок должен быстро пробить линию тренда 2-4 и откататься на всю величину W5. Скорость: прорыв от конца W5 до линии 2-4 должен занять время ≤ длительности W5. Если прорыв медленный (дольше W5) → либо 2-4 построена неправильно, либо W5 ещё продолжается → Терминальная фигура.",
        quote="Когда 5-я волна Импульсной фигуры завершена, правильно построенная линия тренда 2-4 должна быть вскоре пробита... Если прорыв от завершения 5-й волны до линии тренда 2-4 занимает равное количество времени или менее длительности волны-5, то данный прорыв относится к нормальному поведению... Если прорыв занимает больше времени, чем волна-5, вы должны допустить развитие волны-5 в Импульсную фигуру, либо линия тренда 2-4 построена неправильно.",
        page="12-8", section="Каналы / Реальная линия тренда 2-4",
        aw="after wave_5 completion, checking 2-4 breakout speed",
        cons="time(breakout_2_4) <= time(wave_5) => normal ; time(breakout_2_4) > time(wave_5) => wave_5_extended OR wrong_channel",
        notes="Рис.12-11. Терминал: W5 пробивает 2-4 ещё во время формирования."),
    dict(type="rule", strength="mandatory", topic="channeling",
        subtopics=["triangle","wave-identification"],
        statement_ru="Треугольная активность: случайный непреднамеренный прорыв линии тренда (как будто она не имеет никакого значения) — ранний признак Треугольника. Первый ложный прорыв указывает на Треугольную b-волну (не гарантировано). Второй ложный прорыв практически гарантирует Треугольник того или иного Порядка.",
        quote="Случайный, непреднамеренный прорыв установленной линии тренда не гарантирует выявление формирования треугольной b-волны, но практически гарантирует наличие некоторого типа Треугольника того или иного Порядка.",
        page="12-6", section="Каналы / Треугольная активность",
        aw="detecting false breakouts of 0-B trendline",
        cons="count(false_breakouts) == 1: triangle_b_wave_possible ; count(false_breakouts) >= 2: triangle_practically_guaranteed",
        notes="Рис.12-6,12-7,12-8. Признак раннего обнаружения Треугольника."),
    dict(type="rule", strength="mandatory", topic="channeling",
        subtopics=["ending-diagonal","wave-identification"],
        statement_ru="Терминальная активность на каналах: внутри Терминальной фигуры W5 пробивает линию тренда 2-4 более крупной фигуры — это подтверждает Терминальную активность. W3 сегментирована (отмечается 'x'), W5 — Терминальная ('s'). После W4 рынок должен вернуться к минимуму W4 как первая цель.",
        quote="В течение формирования Терминальной фигуры часть ее обычно будет пробивать линию тренда 2-4 более крупной фигуры... Важное замечание: Волновая Теория действительно позволяет спекулировать, когда определённая конфигурация (трендовая) сформирована... активность после волны-(5) должна вернуться к минимуму волны-(4); если этого не происходит, ваша интерпретация неправильная.",
        page="12-8", section="Каналы / Терминальная активность",
        aw="wave_5 breaks larger trendline_2_4 during terminal formation",
        cons="if wave_5 breaks trendline_2_4(larger_degree): confirm terminal_impulse ; after terminal: price MUST reach min(wave_4)",
        notes="Рис.12-10 Диаграммы A/B. Важнейшее подтверждение Терминала."),
    dict(type="rule", strength="mandatory", topic="channeling",
        subtopics=["impulse","rule-of-extension"],
        statement_ru="Форма канала → тип растяжения: Растяжение 1-й → каналы сужаются (клин), W5 не достигает верхней линии тренда. Растяжение 3-й → линии параллельны или почти параллельны независимо от точек касания. Растяжение 5-й → каналы расширяются ('мегафон'), W5 пересекает верхнюю линию ('ложный прорыв').",
        quote="Когда в некоторой волновой последовательности Растянутой является первая волна, построение канала данной фигуры должно напоминать построение канала Терминального движения... Существует несколько вариантов развития канала фигуры с Растянутой 3-й волной. Независимо от того, какие точки касания использованы для построения трендовых линий, эти линии всегда должны быть параллельны или почти параллельны.",
        page="12-10", section="Распознавание Импульсов с помощью каналов",
        aw="identifying extended wave from channel shape",
        cons="channel_converging(upper,lower) => extended_wave_1 ; channel_parallel => extended_wave_3 ; channel_diverging('megaphone') => extended_wave_5",
        notes="Рис.12-12 (Раст.1-й), 12-13 (Раст.3-й), 12-14 (Раст.5-й)."),
    dict(type="rule", strength="mandatory", topic="channeling",
        subtopics=["flat","zigzag","triangle"],
        statement_ru="Распознавание Плоских с помощью каналов: все линии канала должны быть параллельны и горизонтальны, проходить через точки максимума и минимума волны-a. По форме канала определяется разновидность Плоской: Неудавшаяся-b, Неудавшаяся-с, Обыкновенная, Двойная Неудавшаяся, Удлинённая, Неправильная и т.д.",
        quote="Для определения разновидности Плоской, развивающейся на вашем графике, все линии канала должны быть параллельны и горизонтальны, а также должны проходить через точки максимума и минимума волны-а.",
        page="12-10", section="Распознавание Коррекций с помощью каналов / Плоские",
        aw="identifying flat correction type via channel",
        cons="flat_channel: parallel AND horizontal, passing through max(wave_a) AND min(wave_a) ; flat_type determined by relative position of waves b and c within channel",
        notes="Рис.12-16a (стр.12-13): все разновидности Плоских."),
]

n = int(next_aku_id().split("-")[1]); saved = 0
for d in AKUS:
    aku_id = f"AKU-{n:04d}"
    aku = {
        "id": aku_id, "type": d["type"], "strength": d["strength"], "status": "draft",
        "topic": d["topic"], "subtopics": d["subtopics"],
        "statement_ru": d["statement_ru"], "statement_en": None,
        "source": {"book_id": "neely-mwe-1990", "page": d["page"],
                   "chapter": "Глава 12: Дополнительные Расширения Нили",
                   "section": d["section"], "figure_id": None,
                   "verbatim_quote": {"text": d["quote"], "language": "ru"}},
        "formalization": {"status": "draft", "applies_when": d["aw"],
                          "constraint": d["cons"], "formalization_notes": d["notes"]},
        "aliases": [], "related_aku": [], "contradicts_aku": [],
        "extends_aku": None, "supersedes_aku": None,
        "created_by": "claude", "created_at": now_iso(),
        "review_notes": "Извлечено Claude (PDF ч.3 Гл.12 стр.12-1..12-11, Каналы).",
        "requires_review": True,
    }
    save_aku(aku, aku_path("neely-mwe-1990", 12, "dopolnitelnye-rasshireniya-nili", aku_id))
    saved += 1; n += 1
print(f"Создано AKU (Гл.12 каналы): {saved}")
