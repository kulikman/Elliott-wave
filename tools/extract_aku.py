#!/usr/bin/env python3
"""
extract_aku.py — Извлечение AKU из секции через Claude API.

Запуск:
  python tools/extract_aku.py \
    --book-id neely-mwe-1990 \
    --chapter 2 \
    --section "Определение моноволны" \
    --pass-type definitions

pass-type: definitions | mandatory_rules | conditional_rules | heuristics | exceptions | patterns
"""

import argparse
import sys
import yaml
import re
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools._lib import config
from tools._lib.config import (
    EXTRACTED_DIR, SCHEMAS_DIR, AKU_DIR, DOCS_DIR,
    EXTRACTION_MODEL, MAX_AKU_PER_REQUEST, MAX_SECTION_WORDS,
)
from tools._lib.anthropic_client import get_client, call_with_retry
from tools._lib.aku_io import (
    load_golden_examples, parse_yaml_from_llm_response,
    next_aku_id, save_aku, aku_path, now_iso, load_aku,
)
from tools._lib.log import info, ok, warn, error, step, section
from tools.validate_aku import validate_aku, load_taxonomy, load_book_ids, load_all_aku_ids


PASS_TYPES = ["definitions", "mandatory_rules", "conditional_rules", "heuristics", "exceptions", "patterns"]


# ── Загрузка контекста ────────────────────────────────────────────────────────

def load_taxonomy_list() -> str:
    with open(SCHEMAS_DIR / "taxonomy.yaml", "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    slugs = []
    for group in data.get("groups", {}).values():
        for topic in group.get("topics", []):
            slugs.append(f"  - {topic['slug']}: {topic.get('name', '')}")
    return "\n".join(slugs)


def load_schema_summary() -> str:
    """Краткое резюме схемы AKU для промпта."""
    return """Обязательные поля:
- id: AKU-XXXX (используй предоставленный следующий_id)
- type: rule | definition | pattern | heuristic | exception | relation | example
- strength: mandatory | conditional | heuristic | controversial
- status: draft  (всегда draft при первичном извлечении)
- topic: (только из списка топиков)
- statement_ru: чёткая формулировка на русском
- source.book_id: neely-mwe-1990
- source.page: номер страницы
- source.verbatim_quote.text: дословная цитата из текста
- source.verbatim_quote.language: ru
- formalization.status: not_attempted  (всегда при первичном извлечении)
- created_by: claude
- created_at: ISO 8601
- requires_review: true | false"""


def load_chapter_map(book_id: str) -> dict:
    map_path = EXTRACTED_DIR / book_id / "chapter-map.yaml"
    if not map_path.exists():
        raise FileNotFoundError(
            f"chapter-map.yaml не найден: {map_path}\n"
            f"Запусти: python tools/chapter_map.py --book-id {book_id}"
        )
    with open(map_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_section_text(book_id: str, chapter_num: int, section_title: str) -> tuple[str, str, int, int]:
    """
    Извлекает текст секции из full-text.md по chapter-map.yaml.
    Возвращает (text, matched_section_title, char_start, char_end).
    """
    chapter_map = load_chapter_map(book_id)
    full_text_path = EXTRACTED_DIR / book_id / "full-text.md"

    with open(full_text_path, "r", encoding="utf-8") as f:
        full_text = f.read()

    # Находим главу
    chapter = None
    for ch in chapter_map.get("chapters", []):
        if ch["number"] == chapter_num:
            chapter = ch
            break

    if chapter is None:
        # Нет секций → берём весь текст главы
        raise ValueError(
            f"Глава {chapter_num} не найдена в chapter-map.yaml для {book_id}"
        )

    # Если секция не указана или не найдена → берём всю главу
    if not section_title:
        text = full_text[chapter["char_start"]:chapter["char_end"]]
        return text, chapter["title"], chapter["char_start"], chapter["char_end"]

    # Ищем секцию по title (нечёткое совпадение)
    sections = chapter.get("sections", [])
    matched = None
    section_title_lower = section_title.lower()

    for sec in sections:
        if section_title_lower in sec["title"].lower() or sec["title"].lower() in section_title_lower:
            matched = sec
            break

    if matched is None:
        # Fallback: вся глава
        warn(f"Секция '{section_title}' не найдена точно. Использую всю главу {chapter_num}.")
        text = full_text[chapter["char_start"]:chapter["char_end"]]
        return text, chapter["title"], chapter["char_start"], chapter["char_end"]

    text = full_text[matched["char_start"]:matched["char_end"]]
    return text, matched["title"], matched["char_start"], matched["char_end"]


def split_into_subsections(text: str, max_words: int) -> list[str]:
    """Разбивает большой текст на части по max_words слов."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), max_words):
        chunk = " ".join(words[i:i + max_words])
        chunks.append(chunk)
    return chunks


# ── Промпты ───────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Ты — специалист по извлечению знаний из книг по волновому анализу Эллиотта.
Твоя задача: извлекать точные Atomic Knowledge Units (AKU) из текста.

КРИТИЧЕСКИЕ ПРАВИЛА:
1. ТОЛЬКО явные утверждения из текста — никаких выводов или интерпретаций
2. Каждый AKU = одна неделимая единица знания
3. verbatim_quote — дословная цитата, которая ЕСТЬ в предоставленном тексте
4. status всегда: draft
5. formalization.status всегда: not_attempted
6. requires_review: true если есть малейшее сомнение
7. Выводи ТОЛЬКО валидный YAML, никакого текста вокруг"""


EXTRACTION_PROMPTS = {
    "definitions": """Извлекай ТОЛЬКО явные определения терминов.
Определение = текст вида "X — это Y" или "X называется/является Y".
НЕ извлекай правила, рекомендации или описания паттернов.""",

    "mandatory_rules": """Извлекай ТОЛЬКО обязательные правила.
Mandatory rule = нарушение делает волновой счёт невозможным.
Маркеры: "не может", "никогда", "невозможно", "обязательно", "всегда", "должна/не должна".
Если сомневаешься mandatory vs heuristic → strength: controversial, requires_review: true.""",

    "conditional_rules": """Извлекай ТОЛЬКО условные правила.
Conditional rule = выполняется при определённом контексте (если X, то Y).
Маркеры: "если", "при условии", "когда", "в случае", "при".
НЕ извлекай безусловные запреты (это mandatory).""",

    "heuristics": """Извлекай ТОЛЬКО практические эвристики.
Heuristic = обычно верно, но допускает исключения.
Маркеры: "как правило", "обычно", "в большинстве случаев", "типично", "часто".""",

    "exceptions": """Извлекай ТОЛЬКО исключения из других правил.
Exception = явное указание что правило X не применяется при условии Y.
Маркеры: "за исключением", "кроме случаев", "не применяется когда", "исключение".""",

    "patterns": """Извлекай описания волновых паттернов (фигур).
Pattern = структурное описание импульса, коррекции или другой волновой фигуры.
Включай: характеристики структуры, количество волн, направление.""",
}


def build_prompt(
    book_title: str,
    chapter_name: str,
    section_name: str,
    pass_type: str,
    section_text: str,
    taxonomy_list: str,
    schema_summary: str,
    golden_examples: list[dict],
    next_id: str,
    max_aku: int,
) -> str:
    examples_yaml = ""
    for ex in golden_examples[:2]:
        examples_yaml += yaml.dump(ex, allow_unicode=True, sort_keys=False) + "\n---\n"

    type_instruction = EXTRACTION_PROMPTS.get(pass_type, EXTRACTION_PROMPTS["definitions"])

    return f"""КНИГА: {book_title}
ГЛАВА: {chapter_name}
СЕКЦИЯ: {section_name}
ТИП ПРОХОДА: {pass_type}

{type_instruction}

МАКСИМУМ AKU: {max_aku} (жёсткий лимит)
СЛЕДУЮЩИЙ_ID: {next_id} (и далее последовательно)

ДОСТУПНЫЕ ТОПИКИ:
{taxonomy_list}

СХЕМА AKU (обязательные поля):
{schema_summary}

ПРИМЕРЫ ХОРОШЕГО AKU:
{examples_yaml}

ТЕКСТ СЕКЦИИ:
---
{section_text}
---

Выведи YAML-список AKU. ТОЛЬКО YAML, никакого текста до или после.
Если подходящих {pass_type} в тексте нет — выведи пустой список: []
"""


# ── Верификация цитат ─────────────────────────────────────────────────────────

def verify_quotes(aku_list: list[dict], section_text: str, full_text: str) -> list[dict]:
    """
    Проверяет что verbatim_quote реально присутствует в тексте.
    Если не найдена → устанавливает requires_review: true и warning.
    """
    for aku in aku_list:
        quote = aku.get("source", {}).get("verbatim_quote", {})
        quote_text = (quote or {}).get("text", "")

        if not quote_text:
            aku["requires_review"] = True
            aku["review_notes"] = "АВТОПРОВЕРКА: verbatim_quote отсутствует"
            continue

        # Нормализуем для сравнения (убираем лишние пробелы, переводы строк)
        norm_quote = re.sub(r"\s+", " ", quote_text.strip().lower())
        norm_section = re.sub(r"\s+", " ", section_text.lower())
        norm_full = re.sub(r"\s+", " ", full_text.lower())

        # Берём первые 80 символов цитаты для поиска
        search_fragment = norm_quote[:80]

        if search_fragment not in norm_section and search_fragment not in norm_full:
            aku["requires_review"] = True
            existing_notes = aku.get("review_notes") or ""
            aku["review_notes"] = (
                f"{existing_notes}\nАВТОПРОВЕРКА: цитата не найдена в тексте — "
                f"возможна галлюцинация"
            ).strip()

    return aku_list


# ── Сохранение AKU ────────────────────────────────────────────────────────────

def save_aku_list(
    aku_list: list[dict],
    book_id: str,
    chapter_num: int,
    chapter_title: str,
) -> list[Path]:
    """Сохраняет AKU в правильные пути, возвращает список путей."""
    slug = re.sub(r"[^\w]", "-", chapter_title.lower())[:30].strip("-")
    slug = re.sub(r"-+", "-", slug)

    saved_paths = []
    for aku in aku_list:
        aku_id = aku.get("id", "AKU-0000")
        path = aku_path(book_id, chapter_num, slug, aku_id)
        save_aku(aku, path)
        saved_paths.append(path)

    return saved_paths


# ── Обновление chapter-map ────────────────────────────────────────────────────

def update_chapter_map(book_id: str, chapter_num: int, section_title: str,
                       pass_type: str, new_aku_ids: list[str]) -> None:
    map_path = EXTRACTED_DIR / book_id / "chapter-map.yaml"
    with open(map_path, "r", encoding="utf-8") as f:
        chapter_map = yaml.safe_load(f)

    for ch in chapter_map.get("chapters", []):
        if ch["number"] != chapter_num:
            continue

        # Обновляем счётчик AKU главы
        ch["aku_count"] = ch.get("aku_count", 0) + len(new_aku_ids)

        # Обновляем секцию
        for sec in ch.get("sections", []):
            if section_title and (
                section_title.lower() in sec["title"].lower()
                or sec["title"].lower() in section_title.lower()
            ):
                if pass_type not in sec.get("extraction_passes_done", []):
                    sec.setdefault("extraction_passes_done", []).append(pass_type)
                sec.setdefault("aku_ids", []).extend(new_aku_ids)
                break

        break

    with open(map_path, "w", encoding="utf-8") as f:
        yaml.dump(chapter_map, f, allow_unicode=True, sort_keys=False, default_flow_style=False)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Извлекает AKU из секции книги через Claude API"
    )
    parser.add_argument("--book-id", required=True)
    parser.add_argument("--chapter", required=True, type=int, help="Номер главы")
    parser.add_argument("--section", default="", help="Название секции (опционально)")
    parser.add_argument("--pass-type", required=True, choices=PASS_TYPES,
                        help="Тип извлекаемых AKU")
    parser.add_argument("--dry-run", action="store_true",
                        help="Не сохранять AKU — только показать что будет извлечено")
    args = parser.parse_args()

    # ── Проверка API ключа ────────────────────────────────────────────────────
    try:
        config.get_api_key()
    except EnvironmentError as e:
        error(str(e))
        sys.exit(1)

    # ── Проверка book_id ──────────────────────────────────────────────────────
    with open(SCHEMAS_DIR / "books.yaml", "r", encoding="utf-8") as f:
        books_data = yaml.safe_load(f)
    books_map = {b["id"]: b for b in books_data.get("books", [])}
    if args.book_id not in books_map:
        error(f"book_id '{args.book_id}' не найден в schemas/books.yaml")
        sys.exit(1)

    book = books_map[args.book_id]
    book_title = book.get("title_ru") or book.get("full_title", args.book_id)

    # ── Загрузка текста секции ────────────────────────────────────────────────
    section_header = f"Извлечение AKU: Гл.{args.chapter} '{args.section or 'вся глава'}'"
    section(section_header)
    info(f"Книга: {book_title}")
    info(f"Тип прохода: {args.pass_type}")

    try:
        sec_text, sec_title, char_start, char_end = get_section_text(
            args.book_id, args.chapter, args.section
        )
    except (FileNotFoundError, ValueError) as e:
        error(str(e))
        sys.exit(1)

    word_count = len(sec_text.split())
    info(f"📖 Секция: '{sec_title}' — {word_count:,} слов")

    # ── Разбивка на подсекции при превышении лимита ───────────────────────────
    if word_count > MAX_SECTION_WORDS:
        warn(f"Секция большая ({word_count} слов > {MAX_SECTION_WORDS}). Разбиваю на части.")
        subsections = split_into_subsections(sec_text, MAX_SECTION_WORDS)
        info(f"Разбито на {len(subsections)} частей")
    else:
        subsections = [sec_text]

    # ── Загрузка контекста для промпта ───────────────────────────────────────
    taxonomy_list = load_taxonomy_list()
    schema_summary = load_schema_summary()
    golden_examples = load_golden_examples(args.pass_type)

    # ── Загрузка full_text для проверки цитат ─────────────────────────────────
    full_text_path = EXTRACTED_DIR / args.book_id / "full-text.md"
    with open(full_text_path, "r", encoding="utf-8") as f:
        full_text = f.read()

    # ── API вызовы ────────────────────────────────────────────────────────────
    client = get_client()
    taxonomy = load_taxonomy()
    book_ids = load_book_ids()
    all_aku_ids = load_all_aku_ids()

    all_collected: list[dict] = []
    total_valid = 0
    total_warned = 0

    # Счётчик ID в памяти — инкрементируется после каждого валидного AKU
    # чтобы батчи не перезаписывали друг друга
    global_id_counter = int(next_aku_id().split("-")[1])

    for part_idx, sub_text in enumerate(subsections, 1):
        if len(subsections) > 1:
            step(f"Часть {part_idx}/{len(subsections)}")

        start_id = f"AKU-{global_id_counter:04d}"
        start_num = global_id_counter

        prompt = build_prompt(
            book_title=book_title,
            chapter_name=f"Глава {args.chapter}",
            section_name=sec_title,
            pass_type=args.pass_type,
            section_text=sub_text,
            taxonomy_list=taxonomy_list,
            schema_summary=schema_summary,
            golden_examples=golden_examples,
            next_id=start_id,
            max_aku=MAX_AKU_PER_REQUEST,
        )

        step(f"🔍 Запрос к Claude API ({EXTRACTION_MODEL})...")

        max_yaml_retries = 2
        raw_response = None
        candidates = []

        for attempt in range(1, max_yaml_retries + 2):
            try:
                raw_response = call_with_retry(
                    client=client,
                    model=EXTRACTION_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    system=SYSTEM_PROMPT,
                    max_tokens=4096,
                    temperature=0.0,
                )
                candidates = parse_yaml_from_llm_response(raw_response)
                break
            except ValueError as e:
                if attempt <= max_yaml_retries:
                    warn(f"Невалидный YAML (попытка {attempt}/{max_yaml_retries}). Повтор...")
                else:
                    error(f"YAML не распарсен после {max_yaml_retries} попыток: {e}")
                    error("Сохраняю сырой ответ в extracted/{book_id}/debug_response.txt")
                    debug_path = EXTRACTED_DIR / args.book_id / "debug_response.txt"
                    debug_path.write_text(raw_response or "", encoding="utf-8")
                    sys.exit(1)

        if not candidates:
            info(f"  → Нет кандидатов {args.pass_type} в этой части")
            continue

        info(f"📝 Найдено кандидатов: {len(candidates)}")

        # ── Проверка цитат ───────────────────────────────────────────────────
        candidates = verify_quotes(candidates, sub_text, full_text)

        # ── Валидация каждого AKU ────────────────────────────────────────────
        valid_candidates = []
        local_counter = start_num
        for aku in candidates:
            # Назначаем ID из глобального счётчика
            aku["id"] = f"AKU-{local_counter:04d}"
            aku["created_at"] = now_iso()
            if not aku.get("created_by"):
                aku["created_by"] = "claude"
            if not aku.get("status"):
                aku["status"] = "draft"

            # DOC-файл не имеет номеров страниц — заполняем автоматически
            src = aku.setdefault("source", {})
            if not src.get("page"):
                src["page"] = f"doc-ch{args.chapter}"
            if not src.get("book_id"):
                src["book_id"] = args.book_id

            errors, warnings_list = validate_aku(aku, Path(""), taxonomy, book_ids, all_aku_ids)

            if errors:
                warn(f"  AKU-{local_counter:04d}: {len(errors)} ошибок валидации — пропускаю")
                for e in errors:
                    warn(f"    {e}")
                continue

            valid_candidates.append(aku)
            local_counter += 1  # инкремент только для валидных
            if warnings_list:
                total_warned += 1
            else:
                total_valid += 1

        all_collected.extend(valid_candidates)
        global_id_counter = local_counter  # обновляем глобальный счётчик

    # ── Итог ─────────────────────────────────────────────────────────────────
    info(f"\n📝 Всего кандидатов: {sum(len(s.split()) for s in subsections) // 1 and len(all_collected)}")
    info(f"✅ Валидных: {total_valid}  |  ⚠️  С предупреждениями: {total_warned}")

    if not all_collected:
        warn("Нет валидных AKU для сохранения")
        sys.exit(0)

    # ── Сохранение ────────────────────────────────────────────────────────────
    if args.dry_run:
        info("\n[DRY RUN] AKU не сохранены. Что было бы создано:")
        for aku in all_collected:
            print(f"  {aku.get('id')}: {aku.get('statement_ru', '')[:60]}...")
        sys.exit(0)

    step("Сохраняю AKU...")

    # Загружаем chapter map для получения названия главы
    chapter_map = load_chapter_map(args.book_id)
    chapter_title = f"глава-{args.chapter}"
    for ch in chapter_map.get("chapters", []):
        if ch["number"] == args.chapter:
            chapter_title = ch["title"]
            break

    saved_paths = save_aku_list(all_collected, args.book_id, args.chapter, chapter_title)

    for p in saved_paths:
        ok(f"  Сохранён: {p.relative_to(p.parent.parent.parent.parent)}")

    # ── Обновляем chapter-map ─────────────────────────────────────────────────
    new_ids = [a["id"] for a in all_collected]
    update_chapter_map(args.book_id, args.chapter, sec_title, args.pass_type, new_ids)

    section("Готово")
    ok(f"💾 Сохранено: {len(saved_paths)} AKU в aku/{args.book_id}/")
    info(f"Следующий шаг: python tools/validate_aku.py aku/{args.book_id}/")
    info(f"Затем: python tools/review_session.py --book-id {args.book_id} --chapter {args.chapter}")


if __name__ == "__main__":
    main()
