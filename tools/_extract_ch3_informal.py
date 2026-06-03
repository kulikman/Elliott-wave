#!/usr/bin/env python3
"""Извлечение Неформальных правил логики Гл.3 (in-session OCR Claude). status=draft."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from tools._lib.aku_io import save_aku, next_aku_id, now_iso, aku_path

AKUS = [
    dict(type="rule", strength="mandatory", topic="length-ratio-rules", subtopics=["fibonacci-ratios"],
        statement_ru="Для всех соотношений Фибоначчи (61.8%, 161.8% и т.д.) допускается отклонение ±4%: соотношение «61.8% длины другой волны» означает фактический диапазон 58–66%. Выражения «почти»/«близко к» означают в пределах 10%.",
        quote="Для всех упомянутых в тексте процентных соотношений Фибоначчи (61,8% 161,8,% и т. д.) допускаются четырехпроцентные отклонения в обе стороны. Если говорится, что длина одной волны составляет 61,8% длины другой, имеется в виду, что фактически она должна находиться в диапазоне 58—66%. ... выражения «почти» и «близко к...» ... должны пониматься как «в пределах 10% от упомянутого значения».",
        page="3-34", section="Неформальные Правила логики / Конвенции измерений",
        fstatus="draft", aw="comparing wave ratio to a Fibonacci value F",
        cons="match(ratio, F) := abs(ratio - F) <= 0.04 * F ; 'almost' := within 10%",
        notes="±4% на Фибоначчи; ±10% для «почти/близко»."),

    dict(type="rule", strength="mandatory", topic="length-ratio-rules", subtopics=["foundations"],
        statement_ru="Если объект измерения при проверке гипотезы не оговорён особо, по умолчанию измеряется ценовая длина волны (а не временная).",
        quote="Если при проверке обоснованности той или иной гипотезы необходимо произвести какие-либо измерения, объект которых ... не оговаривается особо, по умолчанию измеряется ценовая длина волны.",
        page="3-34", section="Неформальные Правила логики / Конвенции измерений",
        fstatus="draft", aw="measuring wave length when dimension unspecified",
        cons="default_measure(wave) := price_length(wave)", notes=None),

    dict(type="definition", strength="mandatory", topic="structural-labels", subtopics=["informal-logic-rules"],
        statement_ru="В Структурных списках семантика скобок: обозначение без скобок — обычная вероятность; в круглых скобках ( ) — вероятность невысока; в квадратных скобках [ ] — крайне низкая вероятность реализации этого структурного обозначения.",
        quote="Квадратные скобки указывают на крайне низкую вероятность возможности реализации предположения о заключенном в них Структурном обозначении, а круглые скобки означают, что вероятность эта невысока – ниже вероятности того, что верными окажутся гипотезы для свободных от скобок Структурных обозначений.",
        page="3-32", section="Неформальные Правила логики",
        fstatus="not_formalizable", aw=None, cons=None,
        notes="Семантика приоритета структурных гипотез: () < без скобок; [] << всё."),

    dict(type="rule", strength="conditional", topic="structural-labels", subtopics=["length-ratio-rules","monowave"],
        statement_ru="Правило 1 (m2/m1 < 38.2%): структурный список возможных обозначений m1 = {:5, (:c3), (x:c3), [:sL3], [:s5]}. Наиболее вероятно :5 (Импульс).",
        quote="справа от заголовка ... Правило 1 располагается следующий Структурный список: {:5/(:c3)/(x:c3)/[:sL3]/[:s5]}",
        page="3-33", section="Неформальные Правила логики / Правило 1",
        fstatus="draft", aw="rule(m1) == 1",
        cons="structure(m1) in {':5', '(:c3)', '(x:c3)', '[:sL3]', '[:s5]'}", notes="Приоритет: :5 наиболее вероятно."),

    dict(type="rule", strength="conditional", topic="structural-labels", subtopics=["length-ratio-rules","monowave"],
        statement_ru="Правило 2 (38.2% ≤ m2/m1 < 61.8%): структурный список m1 = {:5, (:sL3), [:c3], [:s5]}.",
        quote="Правило 2 {:5/(:sL3)/[:c3]/[:s5]}",
        page="3-37", section="Неформальные Правила логики / Правило 2",
        fstatus="draft", aw="rule(m1) == 2",
        cons="structure(m1) in {':5', '(:sL3)', '[:c3]', '[:s5]'}", notes=None),

    dict(type="rule", strength="conditional", topic="structural-labels", subtopics=["length-ratio-rules","monowave"],
        statement_ru="Правило 3 (m2/m1 = 61.8%): структурный список m1 = {:F3, :c3, :s5, 5, (:sL3), [:L5]}. Соотношение 61.8% — граница Импульс/Коррекция, структура m1 наиболее неоднозначна.",
        quote="Правило 3 {:F3/:c3/:s5/5/(:sL3)/[:L5]}",
        page="3-40", section="Неформальные Правила логики / Правило 3",
        fstatus="draft", aw="rule(m1) == 3",
        cons="structure(m1) in {':F3', ':c3', ':s5', '5', '(:sL3)', '[:L5]'}", notes="Граница Импульс/Коррекция."),

    dict(type="rule", strength="mandatory", topic="informal-logic-rules", subtopics=["compaction","wave-identification"],
        statement_ru="Правила соотношений длин нельзя применять к компактным ценовым фигурам, пересекающим свой собственный начальный уровень; работать следует только с базовой Структурой (:3/:5) таких фигур.",
        quote="не применяйте эти Правила к компактным ценовым фигурам, пересекающим свой собственный начальный уровень; работайте только с базовой Структурой таких ценовых фигур.",
        page="3-33", section="Неформальные Правила логики / Правило преобразования обозначений",
        fstatus="draft", aw="figure is compact AND crosses its own start_level",
        cons="apply_length_rules := false ; use base_structure(figure) instead", notes=None),

    dict(type="rule", strength="mandatory", topic="wave-identification", subtopics=["compaction"],
        statement_ru="При переоценке (reassessment) подтверждённой компактной фигуры: если её базовая Структура не соответствует ни одному из условий перечисленных Правил, в фигуре может быть «пропавшая» (missing) волна; несогласующиеся обозначения помещаются в квадратные скобки. Если фигура «не вписывается» в окружение — она часть Сложной конфигурации.",
        quote="Если базовая Структура переоцениваемой компактной ценовой фигуры не соответствует ни одному из перечисленных в соответствующем разделе условий, в ценовой фигуре может быть так называемая «пропавшая» волна ... Если ... компактная ценовая фигура «не вписывается» в окружающие моноволны ... данная ценовая фигура – часть Сложной конфигурации.",
        page="3-34", section="Неформальные Правила логики",
        fstatus="draft", aw="reassessing a compact figure whose base structure fits no rule-condition",
        cons="possible_missing_wave := true OR part_of_complex_formation := true", notes="Связь с пропавшими волнами (Гл.12) и сжатием (Гл.4)."),
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
        "review_notes": "Извлечено Claude через прямое чтение PDF (Гл.3, Неформальные правила логики). Полный текст — ch03-informal-logic.md.",
        "requires_review": True,
    }
    save_aku(aku, aku_path("neely-mwe-1990", 3, "predvaritelnyj-analiz", aku_id))
    saved += 1; n += 1
print(f"Создано AKU (Гл.3 Неформальные правила логики): {saved}")
