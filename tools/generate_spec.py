#!/usr/bin/env python3
"""
generate_spec.py — Генерирует Indicator Spec JSON из verified+formalized AKU.

Запуск:
  python tools/generate_spec.py
  python tools/generate_spec.py --books neely-mwe-1990
"""

import argparse
import json
import sys
import yaml
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools._lib.config import AKU_DIR, SPEC_DIR, SCHEMAS_DIR
from tools._lib.aku_io import load_all_aku
from tools._lib.log import info, ok, warn, step, section


# Маппинг главы Нили → уровень 9-уровневой иерархии (для метаданных spec)
NEELY_LEVELS = {
    1: "1_monowave",
    2: "2_position_rules",
    3: "3_grouping",
    4: "4_pattern_confirmation",
    5: "5_complex_waves",
    6: "6_advanced_logic",
    7: "7_motion_labels",
    8: "8_channels_fibonacci",
    9: "9_trade_decision",
}


def get_next_spec_version() -> str:
    """Определяет следующую версию spec файла."""
    SPEC_DIR.mkdir(parents=True, exist_ok=True)
    existing = sorted(SPEC_DIR.glob("spec_v*.json"))
    if not existing:
        return "1.0"
    last = existing[-1].stem  # spec_v1.0
    try:
        num = float(last.replace("spec_v", ""))
        return f"{num + 1:.1f}"
    except ValueError:
        return "1.0"


def aku_to_spec_rule(aku: dict) -> dict:
    """Конвертирует AKU в правило для spec."""
    form = aku.get("formalization", {})
    source = aku.get("source", {})
    quote = (source.get("verbatim_quote") or {}).get("text", "")

    return {
        "aku_id": aku.get("id"),
        "statement_ru": aku.get("statement_ru", "").strip(),
        "applies_when": (form.get("applies_when") or "").strip() or None,
        "constraint": (form.get("constraint") or "").strip() or None,
        "verbatim_quote": quote[:300] if quote else None,
        "source": f"{source.get('book_id', '?')} p.{source.get('page', '?')}",
        "strength": aku.get("strength"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Генерирует Indicator Spec JSON из verified+formalized AKU"
    )
    parser.add_argument("--books", default=None,
                        help="Фильтр по book_id через запятую (по умолчанию все)")
    parser.add_argument("--include-draft-formalization", action="store_true",
                        help="Включить AKU с formalization.status=draft (по умолчанию только verified)")
    args = parser.parse_args()

    # ── Загрузка AKU ──────────────────────────────────────────────────────────
    all_aku = load_all_aku(status_filter="verified")

    books_filter = set(args.books.split(",")) if args.books else None
    if books_filter:
        all_aku = [a for a in all_aku if a.get("source", {}).get("book_id") in books_filter]

    # Фильтр: только mandatory/conditional + formalization verified (или draft если флаг)
    allowed_form_statuses = {"verified"}
    if args.include_draft_formalization:
        allowed_form_statuses.add("draft")

    eligible = []
    skipped_no_form = 0
    skipped_strength = 0

    for aku in all_aku:
        strength = aku.get("strength")
        if strength not in {"mandatory", "conditional"}:
            skipped_strength += 1
            continue

        form = aku.get("formalization", {})
        form_status = form.get("status", "not_attempted")

        # Правила без формализации всё равно включаем в spec (без constraint)
        # но помечаем как needs_formalization
        if form_status not in allowed_form_statuses and form_status != "not_formalizable":
            if form_status == "not_attempted":
                skipped_no_form += 1
            # Включаем но без constraint
        eligible.append(aku)

    section("Генерация Indicator Spec")
    info(f"Всего verified AKU: {len(all_aku)}")
    info(f"Прошли фильтр: {len(eligible)}")
    info(f"  Пропущено (не mandatory/conditional): {skipped_strength}")
    info(f"  Без формализации (включены без constraint): {skipped_no_form}")

    if not eligible:
        warn("Нет AKU для включения в spec.")
        warn("Нужны verified AKU с strength=mandatory|conditional.")
        sys.exit(0)

    # ── Группировка по топикам и паттернам ───────────────────────────────────
    step("Группирую по паттернам и топикам...")

    # Паттерны — основные волновые структуры
    pattern_topics = {
        "impulse", "impulse-extension", "leading-diagonal", "ending-diagonal",
        "zigzag", "double-zigzag", "triple-zigzag",
        "flat", "triangle", "combination", "x-wave",
    }

    patterns: dict[str, dict] = defaultdict(lambda: {
        "mandatory_rules": [], "conditional_rules": [], "definitions": [], "other": []
    })
    neely_levels: dict[str, list] = defaultdict(list)
    all_rules_by_topic: dict[str, list] = defaultdict(list)

    for aku in eligible:
        topic = aku.get("topic", "unknown")
        strength = aku.get("strength")
        aku_type = aku.get("type")
        rule = aku_to_spec_rule(aku)

        # Паттерны
        if topic in pattern_topics:
            if strength == "mandatory":
                patterns[topic]["mandatory_rules"].append(rule)
            elif strength == "conditional":
                patterns[topic]["conditional_rules"].append(rule)
            elif aku_type == "definition":
                patterns[topic]["definitions"].append(rule)
            else:
                patterns[topic]["other"].append(rule)

        # Все правила по топикам
        all_rules_by_topic[topic].append(rule)

    # ── Структура spec ────────────────────────────────────────────────────────
    version = get_next_spec_version()

    books_used = sorted({a.get("source", {}).get("book_id", "?") for a in eligible})
    form_verified_count = sum(
        1 for a in eligible
        if (a.get("formalization") or {}).get("status") == "verified"
    )

    spec = {
        "spec_version": version,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generated_from": {
            "books": books_used,
            "aku_total_verified": len(all_aku),
            "aku_in_spec": len(eligible),
            "formalization_verified": form_verified_count,
            "filter": "status=verified AND strength IN (mandatory,conditional)",
        },
        "neely_methodology": {
            "description": "9-уровневая иерархия анализа Нили (NeoWave)",
            "levels": {
                NEELY_LEVELS[i]: {
                    "description": desc,
                    "rules": all_rules_by_topic.get(slug, []),
                }
                for i, (slug, desc) in enumerate([
                    ("monowave", "Идентификация моноволн m0, m1, m2..."),
                    ("length-ratio-rules", "7 правил соотношений длин, структурные обозначения"),
                    ("grouping-procedure", "Группировка в поливолны, правило подобия"),
                    ("formal-logic-rules", "Формальные правила подтверждения паттернов"),
                    ("x-wave", "Сложные поливолны, x-волны"),
                    ("energy-rating", "Рейтинг энергии, продвинутые правила логики"),
                    ("motion-labels", "Метки Движения Нили"),
                    ("channeling", "Каналы и соотношения Фибоначчи"),
                ], 1)
            },
        },
        "patterns": {
            topic: {
                "mandatory_rules": data["mandatory_rules"],
                "conditional_rules": data["conditional_rules"],
                "definitions": data["definitions"],
            }
            for topic, data in sorted(patterns.items())
            if any([data["mandatory_rules"], data["conditional_rules"], data["definitions"]])
        },
        "universal_rules": {
            topic: rules
            for topic, rules in sorted(all_rules_by_topic.items())
            if topic not in pattern_topics
        },
        "mtf_synchronization": {
            "principle": (
                "Higher timeframe defines structural context (pattern type). "
                "Lower timeframe provides wave detail within that structure."
            ),
            "rules": all_rules_by_topic.get("wave-degree", []),
            "implementation_note": (
                "In Pine Script: use request.security() for higher TF wave count. "
                "Lower TF waves must not contradict higher TF structural labels."
            ),
        },
    }

    # ── Сохранение ────────────────────────────────────────────────────────────
    SPEC_DIR.mkdir(parents=True, exist_ok=True)
    out_path = SPEC_DIR / f"spec_v{version}.json"

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)

    ok(f"Сохранено: {out_path.relative_to(out_path.parent.parent.parent)}")

    section("Итог")
    info(f"Версия spec: {version}")
    info(f"AKU в spec: {len(eligible)}")
    info(f"Паттернов покрыто: {len(patterns)}")
    info(f"С формализованным constraint: {form_verified_count}")

    if form_verified_count < len(eligible):
        warn(f"{len(eligible) - form_verified_count} правил без формализации — Pine Script потребует ручной реализации")

    info(f"\nСпека готова для разработки Pine Script индикатора:")
    info(f"  brain-output/indicator-spec/spec_v{version}.json")


if __name__ == "__main__":
    main()
