#!/usr/bin/env python3
"""
extract_aku_direct.py — Извлечение AKU из отдельного markdown-файла главы.

Используется для глав 2, 3, 4 которые хранятся вне full-text.md и chapter-map.yaml.

Запуск:
  python tools/extract_aku_direct.py \
    --book-id neely-mwe-1990 \
    --chapter 2 \
    --file extracted/neely-mwe-1990/ch02-pdf.md \
    --pass-type definitions \
    --out-dir aku/neely-mwe-1990/ch02-osnovnye-ponyatiya

  python tools/extract_aku_direct.py \
    --book-id neely-mwe-1990 \
    --chapter 4 \
    --file extracted/neely-mwe-1990/ch04-grouping.md \
    --pass-type mandatory_rules \
    --out-dir aku/neely-mwe-1990/ch04-dalnejshie-analiticheskie-postroeniya
"""

import argparse
import re
import sys
import yaml
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools._lib import config
from tools._lib.config import SCHEMAS_DIR, AKU_DIR, EXTRACTION_MODEL, MAX_AKU_PER_REQUEST
from tools._lib.anthropic_client import get_client, call_with_retry
from tools._lib.aku_io import load_golden_examples, parse_yaml_from_llm_response, next_aku_id, save_aku, now_iso
from tools._lib.log import info, ok, warn, error, step
from tools.validate_aku import validate_aku, load_taxonomy, load_book_ids, load_all_aku_ids  # noqa: F401
from tools.extract_aku import (
    load_taxonomy_list, load_schema_summary, build_prompt,
    EXTRACTION_PROMPTS, verify_quotes,
)

PASS_TYPES = ["definitions", "mandatory_rules", "conditional_rules", "heuristics", "exceptions"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book-id", required=True)
    parser.add_argument("--chapter", type=int, required=True)
    parser.add_argument("--file", required=True, help="Путь к markdown-файлу главы")
    parser.add_argument("--pass-type", required=True, choices=PASS_TYPES)
    parser.add_argument("--out-dir", required=True, help="Директория для сохранения AKU")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-aku", type=int, default=MAX_AKU_PER_REQUEST)
    args = parser.parse_args()

    # ── Загрузка текста ────────────────────────────────────────────────────────
    file_path = Path(args.file)
    if not file_path.exists():
        error(f"Файл не найден: {file_path}")
        sys.exit(1)
    section_text = file_path.read_text(encoding="utf-8")
    info(f"Файл: {file_path} ({len(section_text)} символов)")

    # ── Книга ─────────────────────────────────────────────────────────────────
    books_path = SCHEMAS_DIR / "books.yaml"
    with open(books_path, encoding="utf-8") as f:
        books_map = {b["id"]: b for b in yaml.safe_load(f).get("books", [])}
    if args.book_id not in books_map:
        error(f"book_id '{args.book_id}' не найден в schemas/books.yaml")
        sys.exit(1)
    book = books_map[args.book_id]
    book_title = book.get("title_ru") or book.get("full_title", args.book_id)

    # ── Следующий ID ──────────────────────────────────────────────────────────
    taxonomy_list = load_taxonomy_list()
    schema_summary = load_schema_summary()
    golden_examples = load_golden_examples(args.pass_type)

    # ── API вызов ─────────────────────────────────────────────────────────────
    client = get_client()
    all_collected: list[dict] = []
    next_id = next_aku_id()
    info(f"Следующий AKU ID: {next_id}")
    info(f"Тип прохода: {args.pass_type}")

    prompt = build_prompt(
        book_title=book_title,
        chapter_name=f"Глава {args.chapter}",
        section_name=f"Весь файл: {file_path.name}",
        pass_type=args.pass_type,
        section_text=section_text,
        taxonomy_list=taxonomy_list,
        schema_summary=schema_summary,
        golden_examples=golden_examples,
        next_id=next_id,
        max_aku=args.max_aku,
    )

    step(f"Вызов Claude API ({EXTRACTION_MODEL}) …")
    raw = call_with_retry(
        client,
        model=EXTRACTION_MODEL,
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
    ).strip()
    parsed = parse_yaml_from_llm_response(raw)
    if not parsed:
        info(f"  → Нет кандидатов {args.pass_type}")
        return

    # Заполнить source.book_id / page если не проставлены
    for aku in parsed:
        src = aku.setdefault("source", {})
        if not src.get("book_id"):
            src["book_id"] = args.book_id
        if not src.get("page"):
            src["page"] = f"ch{args.chapter:02d}"
        if not src.get("chapter"):
            src["chapter"] = f"Глава {args.chapter}"

    # Верификация цитат
    verified = verify_quotes(parsed, section_text, section_text)
    all_collected.extend(verified)
    info(f"  → Найдено: {len(verified)} AKU")

    if args.dry_run:
        info("=== DRY RUN — не сохраняем ===")
        for a in all_collected:
            info(f"  {a.get('id', '?')} [{a.get('type')}] {a.get('statement_ru', '')[:70]}")
        return

    # ── Валидация и сохранение ────────────────────────────────────────────────
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    taxonomy = load_taxonomy()
    valid_book_ids = load_book_ids()
    all_aku_ids = load_all_aku_ids()

    saved = 0
    for aku in all_collected:
        aku_id = aku.get("id", "")
        dummy_path = out_dir / f"{aku_id}.yaml"
        errs, warns = validate_aku(aku, dummy_path, taxonomy, valid_book_ids, all_aku_ids)
        if errs:
            from tools._lib.log import warn as log_warn
            log_warn(f"  {aku_id}: {len(errs)} ошибок валидации — пропущен")
            for e in errs:
                log_warn(f"    {e}")
            continue
        if warns:
            from tools._lib.log import warn as log_warn
            for w in warns:
                log_warn(f"  {aku_id}: {w}")
        path = out_dir / f"{aku_id}.yaml"
        save_aku(aku, path)
        ok(f"  Сохранён: {path}")
        saved += 1

    ok(f"\n💾 Сохранено {saved}/{len(all_collected)} AKU в {out_dir}")
    info("Следующий шаг: python3 tools/validate_aku.py")


if __name__ == "__main__":
    main()
