#!/usr/bin/env python3
"""Гл.4 PDF ч.2: Циклы 1-3, Сжатие, Подобие (детали). status=draft."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from tools._lib.aku_io import save_aku, next_aku_id, now_iso, aku_path

AKUS = [
    dict(type="rule", strength="mandatory", topic="similarity-rule",
        subtopics=["impulse","correction","grouping-procedure"],
        statement_ru="В Импульсных фигурах подобие длительностей (временное) встречается чаще, чем подобие длин (ценовое). В Корректирующих фигурах — обратная картина: ценовое подобие преобладает над временным.",
        quote="В Импульсных ценовых фигурах подобие длительностей двух соседних волн встречается чаще, чем подобие длин; в Коррективных ценовых фигурах наблюдается обратная картина.",
        page="4-4", section="Правило подобия и баланса / Цена и Время",
        aw="checking similarity for impulse vs correction hypothesis",
        cons="if impulse_hypothesis: prefer time_similarity ; if correction_hypothesis: prefer price_similarity",
        notes=None),
    dict(type="rule", strength="mandatory", topic="grouping-procedure",
        subtopics=["compaction","wave-identification"],
        statement_ru="Цикл 1: присвоить структурные обозначения всем моноволнам графика. Выделить обособленные группы из 3 или 5 моноволн, идентифицировать соответствующую Структурную Серию (A-E). Проверить правила Гл.5-12.",
        quote="Используя Правила и методы, описанные в Главе 3, присваиваем Структурные обозначения всем моноволнам Рисунка 4-6. На отрезке... можно изолировать группу волн, образующих Серию \"F3-c3-L5\".",
        page="4-5", section="Цикл 1",
        aw="starting wave grouping process",
        cons="cycle_1: assign structural_labels → isolate groups of 3 or 5 → match Structural Series A-E",
        notes=None),
    dict(type="rule", strength="mandatory", topic="grouping-procedure",
        subtopics=["compaction","wave-identification"],
        statement_ru="Цикл 2: подтверждённые фигуры Цикла 1 сжимаются (compaction) до базовой структуры :3 или :5. Все внутренние метки между границами сжатой фигуры удаляются. Проводится переоценка (reassessment) — проверяется, не изменилась ли структура соседних волн после сжатия.",
        quote="Все группы волн (Плоская, Зигзаг и Импульс), идентифицированные в Цикле 1, тщательно проверены... Затем они были \"сжаты\"... и сведены к своей базовой Структуре — \":3\" или \":5\"... все обозначения и пометки между границами Компактных ценовых фигур удалены.",
        page="4-6", section="Цикл 2",
        aw="after figure confirmation at Level 4",
        cons="compact(figure) → base_label in {':3', ':5'} ; remove internal labels ; reassess adjacent waves",
        notes="Сжатие открывает следующий уровень иерархии."),
    dict(type="rule", strength="mandatory", topic="grouping-procedure",
        subtopics=["compaction","position-indicators"],
        statement_ru="Цикл 3: если в результате Циклов 1-2 не появилось структурное обозначение с Индикатором положения ':L' (:L3 или :L5), дальнейший прогресс в волновой конструкции невозможен до поступления новых данных. Текущий граф остаётся незавершённым.",
        quote="В течение Цикла 3 структурных обозначений с Индикатором Положения \":L\" не обнаружено, следовательно, дальнейшего прогресса в волновой конструкции не предвидится, пока не поступят новые данные, ведущие к появлению на графике \":L3\" или \":L5\".",
        page="4-7", section="Цикл 3",
        aw="after compaction, checking for :L completion marker",
        cons="if not found(':L3' OR ':L5') in current_group: halt_grouping ; wait for new price data",
        notes="Ключевое условие завершённости поливолны — наличие :L меткий."),
    dict(type="rule", strength="mandatory", topic="wave-identification",
        subtopics=["zigzag","impulse","grouping-procedure"],
        statement_ru="Зигзаг или Импульс? Каждый раз, обнаружив волну ':L5', завершающую предполагаемый Зигзаг, проверяй: три последних сегмента (:5-:F3-:L5) могут быть хвостом Импульса. ВСЕГДА проверяй импульсную гипотезу (правила Гл.5-12) ПРЕЖДЕ чем идентифицировать как Зигзаг. Если Импульс подтверждён — остановиться; если нет — вернуться к Зигзагу.",
        quote="Каждый раз, когда вы обнаруживаете волну с обозначением \":L5\", завершающую предполагаемый Зигзаг, вспоминайте, что Зигзаг может представлять собой три последних сегмента Импульса... всегда проверяйте импульсную гипотезу (применяя для этого правила, перечисленные в Главах 5-12), прежде чем идентифицировать группу волн в качестве Зигзага.",
        page="4-8", section="Зигзаг или Импульс?",
        aw="detecting :5-:F3-:L5 sequence",
        cons="on detect(:5-:F3-:L5): test_impulse_first() ; if impulse_confirmed: label='impulse' ; else: label='zigzag'",
        notes="Это AKU-0166 (уже есть). Здесь детализирован алгоритм проверки."),
]

n = int(next_aku_id().split("-")[1]); saved = 0
for d in AKUS:
    aku_id = f"AKU-{n:04d}"
    aku = {
        "id": aku_id, "type": d["type"], "strength": d["strength"], "status": "draft",
        "topic": d["topic"], "subtopics": d["subtopics"],
        "statement_ru": d["statement_ru"], "statement_en": None,
        "source": {"book_id": "neely-mwe-1990", "page": d["page"],
                   "chapter": "Глава 4: Дальнейшие аналитические построения",
                   "section": d["section"],
                   "figure_id": None, "verbatim_quote": {"text": d["quote"], "language": "ru"}},
        "formalization": {"status": "draft", "applies_when": d["aw"],
                          "constraint": d["cons"], "formalization_notes": d["notes"]},
        "aliases": [], "related_aku": [], "contradicts_aku": [],
        "extends_aku": None, "supersedes_aku": None,
        "created_by": "claude", "created_at": now_iso(),
        "review_notes": "Извлечено Claude (PDF ч.2, Гл.4 стр.4-3..4-8, Три Цикла + Сжатие).",
        "requires_review": True,
    }
    save_aku(aku, aku_path("neely-mwe-1990", 4, "dalnejshie-analiticheskie-postroeniya", aku_id))
    saved += 1; n += 1
print(f"Создано AKU (Гл.4 Циклы+Сжатие): {saved}")
