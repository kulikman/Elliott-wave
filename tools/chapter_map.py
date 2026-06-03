#!/usr/bin/env python3
"""
chapter_map.py — Разбивает full-text.md на главы и секции.

Запуск:
  python tools/chapter_map.py --book-id neely-mwe-1990

Выход:
  extracted/{book_id}/chapter-map.yaml
"""

import argparse
import re
import sys
import yaml
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools._lib.config import EXTRACTED_DIR, SCHEMAS_DIR
from tools._lib.log import info, ok, warn, error, step, section


# ── Паттерны заголовков ────────────────────────────────────────────────────────

# Типичные паттерны заголовков в русских переводах книги Нили:
CHAPTER_PATTERNS = [
    # "  Глава 2 Название" или "  Глава 2. Название" (antiword добавляет 2 пробела)
    re.compile(r"^\s{0,4}(?:ГЛАВА|Глава|CHAPTER|Chapter)\s+(\d+)[.:\s—]*(.*)", re.MULTILINE),
    # Markdown-заголовки первого уровня с цифрой
    re.compile(r"^#{1,2}\s+(\d+)[.:—\s]+(.*)", re.MULTILINE),
]

SECTION_PATTERNS = [
    # Markdown h2/h3 без цифры
    re.compile(r"^#{2,3}\s+([^#\n]{5,})", re.MULTILINE),
    # Строки в верхнем регистре с отступом — типичные заголовки секций в antiword-выводе
    re.compile(r"^\s{1,4}([А-ЯЁA-Z][А-ЯЁA-Z\s\-—:()]{9,60})\s*$", re.MULTILINE),
    # Слова полностью заглавными без отступа
    re.compile(r"^([А-ЯЁA-Z][А-ЯЁA-Z\s\-—:]{9,60})$", re.MULTILINE),
]


def detect_language(text: str) -> str:
    """Определяет основной язык текста."""
    ru_chars = sum(1 for c in text[:2000] if 'Ѐ' <= c <= 'ӿ')
    return "ru" if ru_chars > 50 else "en"


def find_chapters(text: str) -> list[dict]:
    """
    Находит границы глав в тексте.
    Возвращает список: [{number, title, char_start, char_end}]
    """
    matches = []

    for pattern in CHAPTER_PATTERNS:
        for m in pattern.finditer(text):
            try:
                num = int(m.group(1))
                title = m.group(2).strip().rstrip(".:-—")
            except (IndexError, ValueError):
                continue
            matches.append({
                "number": num,
                "title": title or f"Глава {num}",
                "char_start": m.start(),
            })

    if not matches:
        return []

    # Убираем дубли (один и тот же номер из разных паттернов)
    seen: dict[int, dict] = {}
    for m in matches:
        n = m["number"]
        if n not in seen or m["char_start"] < seen[n]["char_start"]:
            seen[n] = m

    ordered = sorted(seen.values(), key=lambda x: x["char_start"])

    # Проставляем char_end
    for i, ch in enumerate(ordered):
        ch["char_end"] = ordered[i + 1]["char_start"] if i + 1 < len(ordered) else len(text)

    return ordered


def find_sections(text: str, char_start: int, char_end: int) -> list[dict]:
    """
    Находит секции внутри текстового диапазона главы.
    """
    chunk = text[char_start:char_end]
    sections_raw = []

    for pattern in SECTION_PATTERNS:
        for m in pattern.finditer(chunk):
            title = m.group(1).strip()
            if len(title) < 5:
                continue
            sections_raw.append({
                "title": title,
                "char_start": char_start + m.start(),
            })

    if not sections_raw:
        return []

    # Убираем дубли по позиции (±50 символов = один заголовок)
    deduped = []
    for s in sorted(sections_raw, key=lambda x: x["char_start"]):
        if deduped and abs(s["char_start"] - deduped[-1]["char_start"]) < 50:
            continue
        deduped.append(s)

    # Проставляем char_end
    for i, sec in enumerate(deduped):
        sec["char_end"] = deduped[i + 1]["char_start"] if i + 1 < len(deduped) else char_end

    result = []
    for sec in deduped:
        chunk_sec = text[sec["char_start"]:sec["char_end"]]
        result.append({
            "title": sec["title"],
            "char_start": sec["char_start"],
            "char_end": sec["char_end"],
            "word_count": len(chunk_sec.split()),
            "extraction_passes_done": [],
            "aku_ids": [],
        })

    return result


def estimate_neely_level(chapter_num: int) -> int | None:
    """Маппинг главы Нили → уровень 9-уровневой иерархии."""
    mapping = {
        2: 1,   # Моноволны
        3: 2,   # Предварительный анализ
        4: 3,   # Группировка
        5: 4,   # Импульсные паттерны
        6: 4,   # Корректирующие паттерны
        7: 5,   # Сложные волны
        8: 5,   # Сложные поливолны
        9: 5,   # Макроволны
        10: 6,  # Продвинутые правила логики
        11: 7,  # Метки Движения
        12: 8,  # Каналы + Фибоначчи
    }
    return mapping.get(chapter_num)


def detect_content_types(text: str) -> list[str]:
    """Грубая эвристика: какие типы AKU может содержать текст."""
    types = []
    text_lower = text.lower()

    definition_keywords = ["определяет", "называется", "является", "это —", "означает", "термин"]
    rule_keywords = ["не может", "никогда", "обязательно", "должна", "нельзя", "запрещено", "всегда"]
    heuristic_keywords = ["как правило", "обычно", "как правило", "в большинстве случаев", "типично"]
    pattern_keywords = ["импульс", "зигзаг", "треугольник", "плоская", "коррекция", "диагональный"]

    if any(kw in text_lower for kw in definition_keywords):
        types.append("definitions")
    if any(kw in text_lower for kw in rule_keywords):
        types.append("mandatory_rules")
    if any(kw in text_lower for kw in heuristic_keywords):
        types.append("heuristics")
    if any(kw in text_lower for kw in pattern_keywords):
        types.append("patterns")

    return types if types else ["unknown"]


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Разбивает full-text.md на главы и секции"
    )
    parser.add_argument("--book-id", required=True, help="ID книги из books.yaml")
    parser.add_argument("--force", action="store_true", help="Перезаписать существующий chapter-map.yaml")
    args = parser.parse_args()

    # ── Проверки ──────────────────────────────────────────────────────────────
    books_path = SCHEMAS_DIR / "books.yaml"
    with open(books_path, "r", encoding="utf-8") as f:
        books_data = yaml.safe_load(f)
    known_ids = {b["id"] for b in books_data.get("books", [])}
    if args.book_id not in known_ids:
        error(f"book_id '{args.book_id}' не найден в schemas/books.yaml")
        sys.exit(1)

    out_dir = EXTRACTED_DIR / args.book_id
    full_text_path = out_dir / "full-text.md"
    map_path = out_dir / "chapter-map.yaml"

    if not full_text_path.exists():
        error(f"Файл не найден: {full_text_path}")
        error(f"Сначала запусти: python tools/ingest.py ... --book-id {args.book_id}")
        sys.exit(1)

    if map_path.exists() and not args.force:
        warn(f"chapter-map.yaml уже существует: {map_path}")
        warn("Используй --force чтобы перезаписать")
        sys.exit(0)

    # ── Чтение текста ─────────────────────────────────────────────────────────
    section(f"Chapter Map: {args.book_id}")

    with open(full_text_path, "r", encoding="utf-8") as f:
        text = f.read()

    info(f"Текст загружен: {len(text):,} символов, ~{len(text.split()):,} слов")
    info(f"Язык: {detect_language(text)}")

    # ── Поиск глав ────────────────────────────────────────────────────────────
    step("Ищу главы...")
    chapters_raw = find_chapters(text)

    if not chapters_raw:
        warn("Автоматическое определение глав не удалось.")
        warn("Создаю chapter-map.yaml с флагом manual_split_required: true")
        warn("Отредактируй файл вручную, заполнив границы глав.")

        fallback_map = {
            "book_id": args.book_id,
            "mapped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "map_version": "1.0",
            "total_chars": len(text),
            "total_words": len(text.split()),
            "manual_split_required": True,
            "chapters": [{
                "number": 1,
                "title": "Весь текст (требует ручного разбиения)",
                "char_start": 0,
                "char_end": len(text),
                "word_count": len(text.split()),
                "neely_level": None,
                "sections": [],
                "extraction_status": "pending",
                "aku_count": 0,
            }],
        }
        with open(map_path, "w", encoding="utf-8") as f:
            yaml.dump(fallback_map, f, allow_unicode=True, sort_keys=False)
        warn(f"Создан: {map_path}")
        warn("Необходимо ручное редактирование перед извлечением AKU")
        sys.exit(0)

    info(f"Найдено глав: {len(chapters_raw)}")

    # ── Детализация: секции внутри каждой главы ───────────────────────────────
    step("Ищу секции внутри глав...")
    chapters_full = []

    for ch in chapters_raw:
        ch_text = text[ch["char_start"]:ch["char_end"]]
        sections_list = find_sections(text, ch["char_start"], ch["char_end"])

        info(f"  Гл.{ch['number']}: '{ch['title']}' — "
             f"{len(ch_text.split()):,} слов, {len(sections_list)} секций")

        chapters_full.append({
            "number": ch["number"],
            "title": ch["title"],
            "char_start": ch["char_start"],
            "char_end": ch["char_end"],
            "word_count": len(ch_text.split()),
            "neely_level": estimate_neely_level(ch["number"]),
            "sections": sections_list,
            "extraction_status": "pending",
            "aku_count": 0,
        })

    # ── Сохранение ────────────────────────────────────────────────────────────
    step("Сохраняю chapter-map.yaml")

    chapter_map = {
        "book_id": args.book_id,
        "mapped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "map_version": "1.0",
        "total_chars": len(text),
        "total_words": len(text.split()),
        "manual_split_required": False,
        "chapters": chapters_full,
    }

    with open(map_path, "w", encoding="utf-8") as f:
        yaml.dump(chapter_map, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

    ok(f"Сохранено: {map_path.relative_to(map_path.parent.parent.parent)}")

    # ── Статистика ────────────────────────────────────────────────────────────
    section("Результат")
    info(f"Всего глав: {len(chapters_full)}")
    total_sections = sum(len(ch["sections"]) for ch in chapters_full)
    info(f"Всего секций: {total_sections}")

    print("\n  Карта глав:")
    for ch in chapters_full:
        lvl = f" [уровень {ch['neely_level']}]" if ch["neely_level"] else ""
        print(f"  Гл.{ch['number']:2d}{lvl}: {ch['title'][:50]} — {ch['word_count']:,} слов, {len(ch['sections'])} секций")

    ok(f"\nСледующий шаг:")
    info(f"python tools/extract_aku.py --book-id {args.book_id} --chapter 2 --section \"...\" --pass-type definitions")


if __name__ == "__main__":
    main()
