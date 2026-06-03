#!/usr/bin/env python3
"""
review_session.py — Интерактивная верификация AKU человеком.

Запуск:
  python tools/review_session.py --book-id neely-mwe-1990
  python tools/review_session.py --book-id neely-mwe-1990 --chapter 2
  python tools/review_session.py --book-id neely-mwe-1990 --only-flagged
"""

import argparse
import sys
import yaml
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools._lib.config import AKU_DIR, EXTRACTED_DIR
from tools._lib.aku_io import load_aku, save_aku, now_iso
from tools._lib.log import section, info, ok, warn, error


# ── Загрузка AKU для ревью ────────────────────────────────────────────────────

def load_aku_for_review(book_id: str, chapter: int | None, only_flagged: bool) -> list[tuple[Path, dict]]:
    """Загружает draft AKU из нужной директории."""
    base_dir = AKU_DIR / book_id

    if not base_dir.exists():
        return []

    results = []
    pattern = f"ch{chapter:02d}-*" if chapter else "*"

    for yaml_file in sorted(base_dir.glob(f"{pattern}/*.yaml")):
        try:
            data = load_aku(yaml_file)
        except Exception as e:
            warn(f"Не удалось загрузить {yaml_file.name}: {e}")
            continue

        if data.get("status") != "draft":
            continue
        if only_flagged and not data.get("requires_review"):
            continue

        results.append((yaml_file, data))

    return results


# ── Отображение AKU ───────────────────────────────────────────────────────────

def display_aku(data: dict, index: int, total: int, full_text: str | None = None) -> None:
    """Красивый вывод AKU для верификации."""
    aku_id = data.get("id", "?")
    aku_type = data.get("type", "?")
    topic = data.get("topic", "?")
    strength = data.get("strength", "?")
    requires_review = data.get("requires_review", False)

    flag = " 🚩" if requires_review else ""
    print(f"\n{'═' * 60}")
    print(f"  {aku_id} [{index}/{total}] — {aku_type} / {topic}{flag}")
    print(f"  strength: {strength}")
    print(f"{'═' * 60}")

    # Statement
    statement = data.get("statement_ru", "")
    print(f"\n📌 Утверждение:")
    # Переносим длинные строки
    words = statement.split()
    line = ""
    for word in words:
        if len(line) + len(word) > 65:
            print(f"   {line}")
            line = word
        else:
            line = (line + " " + word).strip()
    if line:
        print(f"   {line}")

    # Цитата
    source = data.get("source", {})
    quote = (source.get("verbatim_quote") or {}).get("text", "")
    page = source.get("page", "?")
    chapter_ref = source.get("chapter", "")

    print(f"\n📖 Цитата (стр. {page}{', ' + chapter_ref if chapter_ref else ''}):")
    if quote:
        # Обрезаем длинную цитату
        display_quote = quote[:300] + "..." if len(quote) > 300 else quote
        print(f"   «{display_quote}»")
    else:
        print("   ⚠️  ЦИТАТА ОТСУТСТВУЕТ")

    # Контекст из full_text если есть
    if full_text and quote:
        import re
        norm_quote = re.sub(r"\s+", " ", quote[:60].strip().lower())
        norm_full = re.sub(r"\s+", " ", full_text.lower())
        pos = norm_full.find(norm_quote)
        if pos > -1:
            ctx_start = max(0, pos - 150)
            ctx_end = min(len(full_text), pos + len(quote) + 150)
            ctx = full_text[ctx_start:ctx_end].replace("\n", " ")
            ctx = re.sub(r"\s+", " ", ctx)
            print(f"\n🔍 Контекст в тексте:")
            print(f"   ...{ctx}...")
        else:
            print(f"\n⚠️  Цитата не найдена в full-text.md — возможна галлюцинация!")

    # Формализация (если есть)
    form = data.get("formalization", {})
    if form.get("constraint"):
        print(f"\n⚙️  Формализация:")
        print(f"   Когда: {form.get('applies_when', '?')}")
        print(f"   Правило: {form.get('constraint', '?')}")

    # Заметки
    review_notes = data.get("review_notes")
    if review_notes:
        print(f"\n📝 Заметки: {review_notes}")

    # Связи
    related = data.get("related_aku", [])
    if related:
        print(f"\n🔗 Связанные AKU: {', '.join(related)}")


# ── Интерактивный ввод ────────────────────────────────────────────────────────

def prompt_action() -> str:
    """Запрашивает действие у пользователя."""
    print("\n" + "─" * 60)
    print("  [v] верифицировать  [d] оспорить  [e] редактировать заметки")
    print("  [s] пропустить      [q] выйти     [?] показать ещё раз")
    print("─" * 60)
    while True:
        try:
            action = input("  Действие: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            return "q"
        if action in {"v", "d", "e", "s", "q", "?"}:
            return action
        print("  Введи одну из букв: v / d / e / s / q / ?")


# ── Обработка действий ────────────────────────────────────────────────────────

def action_verify(data: dict, filepath: Path) -> None:
    data["status"] = "verified"
    data["requires_review"] = False
    save_aku(data, filepath)
    ok(f"  ✅ {data['id']} → verified")


def action_dispute(data: dict, filepath: Path) -> None:
    try:
        reason = input("  Причина (Enter чтобы пропустить): ").strip()
    except (KeyboardInterrupt, EOFError):
        reason = ""

    data["status"] = "disputed"
    if reason:
        existing = data.get("review_notes") or ""
        data["review_notes"] = f"{existing}\nOPPOSED: {reason}".strip()
    save_aku(data, filepath)
    warn(f"  ⚠️  {data['id']} → disputed")


def action_edit_notes(data: dict, filepath: Path) -> None:
    current = data.get("review_notes") or ""
    if current:
        print(f"  Текущие заметки: {current}")
    try:
        new_notes = input("  Новые заметки: ").strip()
    except (KeyboardInterrupt, EOFError):
        new_notes = ""

    if new_notes:
        data["review_notes"] = new_notes
        save_aku(data, filepath)
        ok(f"  📝 Заметки обновлены")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Интерактивная верификация AKU"
    )
    parser.add_argument("--book-id", required=True)
    parser.add_argument("--chapter", type=int, default=None, help="Фильтр по номеру главы")
    parser.add_argument("--only-flagged", action="store_true",
                        help="Показывать только AKU с requires_review=true")
    args = parser.parse_args()

    # ── Загрузка AKU ──────────────────────────────────────────────────────────
    aku_list = load_aku_for_review(args.book_id, args.chapter, args.only_flagged)

    if not aku_list:
        filter_desc = f" (глава {args.chapter})" if args.chapter else ""
        filter_flag = " с флагом requires_review" if args.only_flagged else ""
        warn(f"Нет draft AKU{filter_desc}{filter_flag} для книги '{args.book_id}'")
        info(f"Запусти сначала: python tools/extract_aku.py --book-id {args.book_id} ...")
        sys.exit(0)

    # ── Загрузка full-text для контекста ──────────────────────────────────────
    full_text = None
    full_text_path = EXTRACTED_DIR / args.book_id / "full-text.md"
    if full_text_path.exists():
        with open(full_text_path, "r", encoding="utf-8") as f:
            full_text = f.read()

    section(f"Review Session: {args.book_id}")
    chapter_info = f" | Глава {args.chapter}" if args.chapter else ""
    info(f"AKU для ревью: {len(aku_list)}{chapter_info}")
    info("Нажми Ctrl+C или введи 'q' для выхода")

    # ── Статистика сессии ─────────────────────────────────────────────────────
    stats = {"verified": 0, "disputed": 0, "skipped": 0}
    total = len(aku_list)

    for idx, (filepath, data) in enumerate(aku_list, 1):
        while True:
            display_aku(data, idx, total, full_text)
            action = prompt_action()

            if action == "v":
                action_verify(data, filepath)
                stats["verified"] += 1
                break
            elif action == "d":
                action_dispute(data, filepath)
                stats["disputed"] += 1
                break
            elif action == "e":
                action_edit_notes(data, filepath)
                # После редактирования заметок — показываем снова
                continue
            elif action == "s":
                print(f"  ⏭  {data['id']} пропущен")
                stats["skipped"] += 1
                break
            elif action == "q":
                break
            elif action == "?":
                continue  # Показать снова

        if action == "q":
            info("\nСессия прервана")
            break

    # ── Финальная статистика ──────────────────────────────────────────────────
    section("Итог сессии")
    reviewed = stats["verified"] + stats["disputed"]
    print(f"  ✅ Верифицировано: {stats['verified']}")
    print(f"  ⚠️  Оспорено:       {stats['disputed']}")
    print(f"  ⏭  Пропущено:      {stats['skipped']}")
    print(f"  📊 Всего:          {total}")

    if total > 0:
        pct = stats["verified"] / total * 100
        gate_status = "✅ ВЫШЕ ПОРОГА" if pct >= 80 else "❌ НИЖЕ ПОРОГА (нужно ≥80%)"
        print(f"\n  Gate Фазы 1: {stats['verified']}/{total} = {pct:.1f}% — {gate_status}")

    info(f"\nСледующий шаг:")
    if stats["verified"] > 0:
        info(f"  python tools/formalize_aku.py --book-id {args.book_id}")


if __name__ == "__main__":
    main()
