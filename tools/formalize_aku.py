#!/usr/bin/env python3
"""
formalize_aku.py — Формализация правил (отдельный проход после верификации).

Добавляет applies_when + constraint в псевдокоде к verified mandatory/conditional AKU.

Запуск:
  python tools/formalize_aku.py --book-id neely-mwe-1990
  python tools/formalize_aku.py --book-id neely-mwe-1990 --aku-id AKU-0004
  python tools/formalize_aku.py --book-id neely-mwe-1990 --dry-run
"""

import argparse
import sys
import yaml
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools._lib import config
from tools._lib.config import AKU_DIR, EXTRACTED_DIR, SCHEMAS_DIR, FORMALIZATION_MODEL
from tools._lib.anthropic_client import get_client, call_with_retry
from tools._lib.aku_io import load_aku, save_aku, now_iso
from tools._lib.log import info, ok, warn, error, step, section


SYSTEM_PROMPT = """Ты формализуешь правила волнового анализа Эллиотта в псевдокоде.

ПРАВИЛА:
1. Только для verified mandatory или conditional правил
2. Используй только то что явно есть в statement_ru и verbatim_quote
3. Псевдокод должен быть понятен разработчику Pine Script
4. Если правило не поддаётся формализации — укажи formalization_status: not_formalizable с объяснением
5. НЕ добавляй ничего чего нет в исходном правиле"""


def build_formalization_prompt(aku: dict, context_text: str | None = None) -> str:
    aku_yaml = yaml.dump(aku, allow_unicode=True, sort_keys=False)

    ctx_block = ""
    if context_text:
        # Берём контекст вокруг цитаты
        quote = (aku.get("source", {}).get("verbatim_quote") or {}).get("text", "")
        if quote and quote in context_text:
            pos = context_text.find(quote[:50])
            if pos > -1:
                ctx = context_text[max(0, pos - 300): pos + len(quote) + 300]
                ctx_block = f"\nКОНТЕКСТ ИЗ КНИГИ (±300 символов вокруг цитаты):\n---\n{ctx}\n---\n"

    return f"""Формализуй следующий AKU в псевдокоде для алгоритма определения волн Эллиотта.
{ctx_block}
AKU:
---
{aku_yaml}
---

Выведи ТОЛЬКО YAML блок formalization:

formalization:
  status: draft  # или not_formalizable
  applies_when: |
    # Псевдокод: когда применяется правило
    # Пример: pattern == 'impulse' AND current_wave == 2
  constraint: |
    # Псевдокод: само ограничение
    # Пример: low(wave_2) > low(wave_1_start)
  formalization_notes: |
    # Опционально: что осталось неясным, почему не формализуемо

Только YAML, никакого текста вокруг."""


def load_aku_for_formalization(book_id: str, aku_id: str | None) -> list[tuple[Path, dict]]:
    """Загружает verified AKU без формализации."""
    base_dir = AKU_DIR / book_id
    if not base_dir.exists():
        return []

    results = []
    for yaml_file in sorted(base_dir.rglob("*.yaml")):
        try:
            data = load_aku(yaml_file)
        except Exception:
            continue

        if data.get("status") != "verified":
            continue
        if data.get("type") not in {"rule"}:
            continue
        if data.get("strength") not in {"mandatory", "conditional"}:
            continue
        form = data.get("formalization", {})
        # draft = формализация начата но не завершена — тоже обрабатываем
        if form.get("status") not in {None, "not_attempted", "draft"}:
            continue
        if aku_id and data.get("id") != aku_id:
            continue

        results.append((yaml_file, data))

    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Формализует verified AKU правила в псевдокод"
    )
    parser.add_argument("--book-id", required=True)
    parser.add_argument("--aku-id", default=None, help="Конкретный AKU ID (иначе все)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        config.get_api_key()
    except EnvironmentError as e:
        error(str(e))
        sys.exit(1)

    aku_list = load_aku_for_formalization(args.book_id, args.aku_id)

    if not aku_list:
        warn(f"Нет verified правил без формализации для '{args.book_id}'")
        info("Сначала верифицируй AKU: python tools/review_session.py ...")
        sys.exit(0)

    # Загружаем full-text для контекста
    full_text = None
    ft_path = EXTRACTED_DIR / args.book_id / "full-text.md"
    if ft_path.exists():
        with open(ft_path, "r", encoding="utf-8") as f:
            full_text = f.read()

    section(f"Формализация AKU: {args.book_id}")
    info(f"AKU для формализации: {len(aku_list)}")

    client = get_client()
    done = 0
    failed = 0

    for filepath, aku in aku_list:
        aku_id = aku.get("id", "?")
        step(f"{aku_id}: {aku.get('statement_ru', '')[:60]}...")

        prompt = build_formalization_prompt(aku, full_text)

        try:
            response = call_with_retry(
                client=client,
                model=FORMALIZATION_MODEL,
                messages=[{"role": "user", "content": prompt}],
                system=SYSTEM_PROMPT,
                max_tokens=1024,
                temperature=0.0,
            )
        except Exception as e:
            error(f"  API ошибка: {e}")
            failed += 1
            continue

        # Парсим ответ
        try:
            import yaml as _yaml
            import re

            # Убираем markdown fence если есть (с переносом или без)
            text = response.strip()
            fence_match = re.search(r"```(?:yaml)?\s*\n?(.*?)```", text, re.DOTALL)
            if fence_match:
                text = fence_match.group(1).strip()
            # На случай если остались обратные кавычки в начале строки
            text = re.sub(r"^```\w*\s*", "", text)
            text = re.sub(r"```\s*$", "", text).strip()

            # Убираем ведущий ключ "formalization:" если есть
            parsed = _yaml.safe_load(text)
            if isinstance(parsed, dict) and "formalization" in parsed:
                form_data = parsed["formalization"]
            elif isinstance(parsed, dict) and "status" in parsed:
                form_data = parsed
            else:
                raise ValueError(f"Неожиданная структура: {parsed}")

        except Exception as e:
            error(f"  Невалидный ответ: {e}")
            failed += 1
            continue

        if args.dry_run:
            info(f"  [DRY RUN] Формализация для {aku_id}:")
            print(f"    status: {form_data.get('status')}")
            print(f"    applies_when: {str(form_data.get('applies_when', ''))[:80]}...")
            print(f"    constraint: {str(form_data.get('constraint', ''))[:80]}...")
            done += 1
            continue

        # Обновляем AKU
        aku["formalization"] = {
            "status": form_data.get("status", "draft"),
            "applies_when": form_data.get("applies_when"),
            "constraint": form_data.get("constraint"),
            "formalization_notes": form_data.get("formalization_notes"),
        }
        save_aku(aku, filepath)
        ok(f"  ✅ {aku_id} → formalization.status={form_data.get('status')}")
        done += 1

    section("Итог")
    info(f"✅ Формализовано: {done}")
    if failed:
        warn(f"❌ Ошибок: {failed}")
    if not args.dry_run and done > 0:
        info(f"Следующий шаг: python tools/review_session.py --book-id {args.book_id} --only-flagged")
        info(f"Затем: python tools/generate_spec.py")


if __name__ == "__main__":
    main()
