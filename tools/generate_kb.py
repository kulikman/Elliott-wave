#!/usr/bin/env python3
"""
generate_kb.py — Генерирует Knowledge Base из verified AKU.

Запуск:
  python tools/generate_kb.py --topic impulse
  python tools/generate_kb.py --all
"""

import argparse
import sys
import yaml
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools._lib.config import AKU_DIR, KB_DIR, SCHEMAS_DIR
from tools._lib.aku_io import load_all_aku
from tools._lib.log import info, ok, warn, step, section


def load_taxonomy() -> dict:
    with open(SCHEMAS_DIR / "taxonomy.yaml", "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    topics = {}
    for group_key, group in data.get("groups", {}).items():
        for topic in group.get("topics", []):
            topics[topic["slug"]] = {
                "name": topic.get("name", topic["slug"]),
                "group": group_key,
                "note": topic.get("note", ""),
            }
    return topics


def get_all_topic_slugs(taxonomy: dict) -> list[str]:
    return sorted(taxonomy.keys())


def aku_to_kb_entry(aku: dict) -> str:
    """Форматирует один AKU как строку в KB."""
    aku_id = aku.get("id", "?")
    statement = aku.get("statement_ru", "").strip()
    strength = aku.get("strength", "")
    source = aku.get("source", {})
    page = source.get("page", "?")
    book_id = source.get("book_id", "?")
    quote = (source.get("verbatim_quote") or {}).get("text", "")

    # Заголовок с ID и силой правила
    strength_icon = {"mandatory": "🔴", "conditional": "🟡", "heuristic": "🟢", "controversial": "⚪"}.get(strength, "")
    lines = [f"**{statement}** ({aku_id}) {strength_icon}"]

    if quote:
        short_quote = quote[:200] + "..." if len(quote) > 200 else quote
        lines.append(f"> «{short_quote}»")

    lines.append(f"*Источник: {book_id}, стр. {page}*")

    form = aku.get("formalization", {})
    if form.get("status") in {"draft", "verified"} and form.get("constraint"):
        lines.append(f"\n```")
        if form.get("applies_when"):
            lines.append(f"Когда: {form['applies_when'].strip()}")
        lines.append(f"Правило: {form['constraint'].strip()}")
        lines.append("```")

    return "\n".join(lines)


def generate_topic_kb(topic_slug: str, topic_info: dict, aku_list: list[dict]) -> str:
    """Генерирует markdown файл KB для одного топика."""
    topic_name = topic_info.get("name", topic_slug)
    book_counts: dict[str, int] = defaultdict(int)
    for aku in aku_list:
        book_counts[aku.get("source", {}).get("book_id", "?")] += 1

    sources_str = ", ".join(f"{k}: {v}" for k, v in sorted(book_counts.items()))

    lines = [
        f"# {topic_name} — Knowledge Base",
        f"",
        f"> Топик: `{topic_slug}` | AKU verified: {len(aku_list)} | Источники: {sources_str}",
        f"> Сгенерировано: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"",
    ]

    # Группируем по type
    by_type: dict[str, list[dict]] = defaultdict(list)
    for aku in aku_list:
        by_type[aku.get("type", "other")].append(aku)

    type_headers = {
        "definition": "## Определения",
        "rule": "## Правила",
        "pattern": "## Паттерны",
        "heuristic": "## Эвристики",
        "exception": "## Исключения",
        "relation": "## Связи",
        "example": "## Примеры",
    }

    # Сначала обязательные правила
    mandatory = [a for a in by_type.get("rule", []) if a.get("strength") == "mandatory"]
    conditional = [a for a in by_type.get("rule", []) if a.get("strength") == "conditional"]
    heuristics = by_type.get("rule", [])
    heuristics = [a for a in heuristics if a.get("strength") not in {"mandatory", "conditional"}]

    if by_type.get("definition"):
        lines.append("## Определения\n")
        for aku in sorted(by_type["definition"], key=lambda x: x.get("id", "")):
            lines.append(aku_to_kb_entry(aku))
            lines.append("")

    if mandatory:
        lines.append("## Обязательные правила\n")
        for i, aku in enumerate(sorted(mandatory, key=lambda x: x.get("id", "")), 1):
            lines.append(f"{i}. {aku_to_kb_entry(aku)}")
            lines.append("")

    if conditional:
        lines.append("## Условные правила\n")
        for i, aku in enumerate(sorted(conditional, key=lambda x: x.get("id", "")), 1):
            lines.append(f"{i}. {aku_to_kb_entry(aku)}")
            lines.append("")

    if by_type.get("heuristic") or heuristics:
        lines.append("## Эвристики\n")
        all_heuristics = by_type.get("heuristic", []) + heuristics
        for aku in sorted(all_heuristics, key=lambda x: x.get("id", "")):
            lines.append(f"- {aku_to_kb_entry(aku)}")
            lines.append("")

    if by_type.get("pattern"):
        lines.append("## Паттерны\n")
        for aku in sorted(by_type["pattern"], key=lambda x: x.get("id", "")):
            lines.append(aku_to_kb_entry(aku))
            lines.append("")

    if by_type.get("exception"):
        lines.append("## Исключения\n")
        for aku in sorted(by_type["exception"], key=lambda x: x.get("id", "")):
            lines.append(f"- {aku_to_kb_entry(aku)}")
            lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Генерирует Knowledge Base из verified AKU")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--topic", help="Конкретный топик (slug из taxonomy.yaml)")
    group.add_argument("--all", action="store_true", help="Генерировать для всех топиков")
    args = parser.parse_args()

    taxonomy = load_taxonomy()

    if args.topic and args.topic not in taxonomy:
        from tools._lib.log import error
        error(f"Топик '{args.topic}' не найден в taxonomy.yaml")
        error(f"Доступные: {', '.join(sorted(taxonomy.keys()))}")
        sys.exit(1)

    # Загружаем все verified AKU
    all_aku = load_all_aku(status_filter="verified")
    if not all_aku:
        warn("Нет verified AKU. Запусти review_session.py для верификации.")
        sys.exit(0)

    info(f"Загружено verified AKU: {len(all_aku)}")

    # Определяем топики для генерации
    if args.all:
        topics_to_generate = get_all_topic_slugs(taxonomy)
    else:
        topics_to_generate = [args.topic]

    KB_DIR.mkdir(parents=True, exist_ok=True)
    generated = 0

    section("Генерация Knowledge Base")

    for topic_slug in topics_to_generate:
        # Фильтруем AKU по топику (основной + subtopics)
        topic_aku = [
            a for a in all_aku
            if a.get("topic") == topic_slug or topic_slug in (a.get("subtopics") or [])
        ]

        if not topic_aku:
            if not args.all:
                warn(f"Нет verified AKU для топика '{topic_slug}'")
            continue

        step(f"Топик '{topic_slug}': {len(topic_aku)} AKU")

        topic_info = taxonomy[topic_slug]
        content = generate_topic_kb(topic_slug, topic_info, topic_aku)

        out_path = KB_DIR / f"{topic_slug}.md"
        out_path.write_text(content, encoding="utf-8")
        ok(f"  Сохранено: {out_path.relative_to(out_path.parent.parent.parent)}")
        generated += 1

    section("Итог")
    info(f"Сгенерировано KB файлов: {generated}")

    if generated > 0:
        info(f"Файлы: brain-output/kb/")
        info(f"Следующий шаг: python tools/generate_spec.py")


if __name__ == "__main__":
    main()
