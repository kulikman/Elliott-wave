#!/usr/bin/env python3
"""Индикаторы положения Гл.3 (3-60..3-64), in-session OCR Claude. status=draft."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from tools._lib.aku_io import save_aku, next_aku_id, now_iso, aku_path

AKUS = [
    dict(type="definition", strength="mandatory", topic="position-indicators", subtopics=["structural-labels"],
        statement_ru="Индикаторы положения (c, F, L, s, sL) — буквенные префиксы Структурных обозначений (:3/:5), описывающие положение волны среди соседних. Базовое обозначение — без индикатора (:3/:5); позиционированное — с индикатором (:F3, :c3, :L3, :L5, :s5, :sL3).",
        quote="Индикаторы положения – это буквенные символы (\"c\", \"F\", \"L\", \"s\" или \"sL\"), предшествующие большинству Структурных обозначений (\":3\" – \"тройкам\", и \":5\" – \"пятеркам\"). ... функция Индикаторов положения заключается в описании ... положения Структурных обозначений волн в контексте ... анализируемого рынка.",
        page="3-60", section="Применение Индикаторов положения",
        fstatus="not_formalizable", aw=None, cons=None, notes=None),
    dict(type="definition", strength="mandatory", topic="structural-series", subtopics=["grouping-procedure"],
        statement_ru="Разделители в Структурных сериях: дефис «-» разграничивает части ОДНОЙ Стандартной фигуры Эллиота; два плюса «++» разграничивают ДВЕ Стандартные фигуры, а также x-волны между ними.",
        quote="Разделитель первого типа (дефис) применяется для разграничения частей одной и той же Стандартной ценовой фигуры Эллиота, а разделитель второго типа (два плюса) – для разграничения двух Стандартных ценовых фигур Эллиота, а также x-волн, возникающих между ними.",
        page="3-61", section="Инструкции",
        fstatus="draft", aw="parsing a structural series string",
        cons="'-' => within one standard figure ; '++' => boundary between figures / x-wave", notes=None),
    dict(type="definition", strength="mandatory", topic="position-indicators", subtopics=["structural-labels"],
        statement_ru=":F3 (первая тройка, First 3) — первый сегмент группы, либо возникает после x:c3, либо между двумя :5. Если две :F3 идут подряд, вторая начинает новую (меньшую) ценовую фигуру.",
        quote="Аббревиатура \":F3\" расшифровывается как \"первая тройка\" (\"First 3\"). Волна с этим Структурным обозначением либо первый сегмент группы, возникающий либо \"x:c3\", либо встречается между двумя \"пятерками\" (\":5\"). Если две \"первые тройки\" (\":F3\") встречаются подряд, значит, второй из них начинается новая ценовая фигура.",
        page="3-61", section="Определения Индикаторов положения / :F3",
        fstatus="draft", aw="assigning :F3 within a group",
        cons="position(:F3) == first(group) OR prev == 'x:c3' OR between two :5 ; two :F3 in a row => second starts new figure", notes=None),
    dict(type="rule", strength="mandatory", topic="position-indicators", subtopics=["structural-labels"],
        statement_ru=":c3 (центральная тройка, Center 3) никогда не может быть первым или последним сегментом последовательности; после неё крупных/резких движений практически не происходит.",
        quote="Эта аббревиатура расшифровывается как \"центральная тройка\" (\"Center 3\"). Волна с таким Структурным обозначением никогда не может быть первым либо последним сегментом последовательности, поэтому после нее крупных и резких движений практически никогда не происходит.",
        page="3-62", section="Определения Индикаторов положения / :c3",
        fstatus="draft", aw="assigning :c3",
        cons="position(:c3) NOT IN {first(seq), last(seq)}", notes=None),
    dict(type="rule", strength="mandatory", topic="x-wave", subtopics=["position-indicators","complexity-rule"],
        statement_ru="x:c3 (центральная тройка в позиции x-волны) никогда не первый/последний сегмент; возникает между Стандартными фигурами, объединяя простые коррекции в более крупные. Её уровень сложности не выше завершённой предшествующей фигуры; следующая фигура обычно на уровень ниже обеих окружающих. :c3 можно преобразовать в x:c3, но не наоборот.",
        quote="Волна с этим Структурным обозначением никогда не может быть первым либо последним сегментом последовательности ... Такая волна возникает между Стандартными ценовыми фигурами Эллиота, объединяя простые коррекции в более крупные конфигурации. ... уровень сложности волны с обозначением \"x:c3\" не может быть выше уровня сложности завершенной ценовой фигуры Эллиота, предшествующей \"x:c3\".",
        page="3-62", section="Определения Индикаторов положения / x:c3",
        fstatus="draft", aw="assigning x:c3 (x-wave linker)",
        cons="position(x:c3) NOT IN {first, last} AND complexity(x:c3) <= complexity(preceding_completed_figure)", notes=None),
    dict(type="rule", strength="mandatory", topic="position-indicators", subtopics=["structural-labels","ending-diagonal","triangle"],
        statement_ru=":sL3 (предпоследняя тройка, second-to-Last 3) — обусловленное обозначение, никогда не первый/последний сегмент, не существует без пары: за :sL3 ВСЕГДА следует :L3. Указывает на формирование Терминала или Треугольника. Единственная допустимая серия: c3-sL3-3-?.",
        quote="Это Структурное обозначение – аббревиатура выражения \"предпоследняя тройка\" (second to Last three (3)). Волна с таким обозначением никогда не может быть ни первым, ни последним сегментом ... За волной с обозначением \":sL3\" всегда следует волна с обозначением \":L3\".",
        page="3-63", section="Определения Индикаторов положения / :sL3",
        fstatus="draft", aw="assigning :sL3",
        cons="position(:sL3) NOT IN {first, last} AND next(:sL3) == ':L3' ; valid series: c3-sL3-3-?", notes="Указывает на Терминал/Треугольник."),
    dict(type="rule", strength="mandatory", topic="position-indicators", subtopics=["structural-labels","ending-diagonal","triangle"],
        statement_ru=":L3 (последняя тройка, Last 3) — последняя из пяти последовательных троек, образующих Терминал или Треугольник. Различение: применить Основные Правила построения Импульса (Гл.5, стр.5-2) — если выполняются, это Терминальный Импульс; если нет — Треугольник.",
        quote="Равно как и \":sL3\", \":L3\" должна быть последней из пяти последовательных \"троек\". Определить тип формирующейся волны (Терминал или Треугольник) вам помогут Правила графических построений основных импульсов ... если ... правила ... выполняются, образуется Терминальный Импульс, если нет – формируется Треугольник.",
        page="3-63", section="Определения Индикаторов положения / :L3",
        fstatus="draft", aw="assigning :L3 as last of five :3",
        cons="position(:L3) == last_of_5_threes ; figure = essential_impulse_rules_hold ? 'terminal' : 'triangle'", notes=None),
    dict(type="definition", strength="mandatory", topic="structural-labels", subtopics=["impulse","position-indicators"],
        statement_ru=":s5 («особенная пятёрка», special five) — функционирует как :L5 (завершает фигуру), но не требует резкого разворота направления; обычно третий сегмент Трендового Импульса с Неудавшейся или Растянутой пятой.",
        quote="Эта аббревиатура расшифровывается как \"необычная (особенная) пятерка\" (special five (5)). ... Функции обозначения \":s5\" схожи с функциями \":L5\", единственное отличие их в том, что для подтверждения волны со структурой \":s5\" не требуется резкого изменения направления движения котировок.",
        page="3-64", section="Структурные обозначения / :s5",
        fstatus="not_formalizable", aw=None, cons=None, notes=None),
]

n = int(next_aku_id().split("-")[1]); saved = 0
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
        "review_notes": "Извлечено Claude через прямое чтение PDF (Гл.3, Индикаторы положения). Полный текст — ch03-position-indicators.md.",
        "requires_review": True,
    }
    save_aku(aku, aku_path("neely-mwe-1990", 3, "predvaritelnyj-analiz", aku_id))
    saved += 1; n += 1
print(f"Создано AKU (Индикаторы положения): {saved}")
