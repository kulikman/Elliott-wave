#!/usr/bin/env python3
"""
AKU Validator v1.0
Elliott Wave Brain

Запуск:
  python tools/validate_aku.py              # проверить все AKU
  python tools/validate_aku.py aku/golden/  # проверить конкретную папку
  python tools/validate_aku.py aku/AKU-0001.yaml  # проверить один файл

Коды выхода:
  0 — все проверки пройдены
  1 — найдены ошибки
"""

import sys
import os
import yaml
import re
from pathlib import Path
from datetime import datetime

# ============================================================
# ЗАГРУЗКА КОНФИГУРАЦИИ
# ============================================================

SCHEMA_DIR = Path(__file__).parent.parent / "schemas"
AKU_DIR = Path(__file__).parent.parent / "aku"


def load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_taxonomy():
    data = load_yaml(SCHEMA_DIR / "taxonomy.yaml")
    slugs = set()
    for group in data.get("groups", {}).values():
        for topic in group.get("topics", []):
            slugs.add(topic["slug"])
    return slugs


def load_book_ids():
    data = load_yaml(SCHEMA_DIR / "books.yaml")
    return {book["id"] for book in data.get("books", [])}


def load_all_aku_ids(skip_file=None):
    ids = set()
    for yaml_file in AKU_DIR.rglob("*.yaml"):
        if skip_file and yaml_file == skip_file:
            continue
        try:
            data = load_yaml(yaml_file)
            if isinstance(data, dict) and "id" in data:
                ids.add(data["id"])
        except Exception:
            pass
    return ids


# ============================================================
# ПРАВИЛА ВАЛИДАЦИИ
# ============================================================

VALID_TYPES = {"rule", "definition", "pattern", "heuristic", "exception", "relation", "example"}
VALID_STRENGTHS = {"mandatory", "conditional", "heuristic", "controversial"}
VALID_STATUSES = {"draft", "verified", "disputed", "deprecated"}
VALID_CREATED_BY = {"claude", "manual", "converted"}
VALID_FORM_STATUSES = {"not_attempted", "not_formalizable", "draft", "verified"}
AKU_ID_PATTERN = re.compile(r"^AKU-\d{4}$")


def validate_aku(data: dict, filepath: Path, taxonomy: set, book_ids: set, all_ids: set) -> list:
    errors = []
    warnings = []

    def err(msg):
        errors.append(f"  ❌ {msg}")

    def warn(msg):
        warnings.append(f"  ⚠️  {msg}")

    # --- ID ---
    aku_id = data.get("id")
    if not aku_id:
        err("Отсутствует поле 'id'")
    elif not AKU_ID_PATTERN.match(str(aku_id)):
        err(f"'id' должен быть в формате AKU-XXXX, получено: '{aku_id}'")

    # --- TYPE ---
    aku_type = data.get("type")
    if not aku_type:
        err("Отсутствует поле 'type'")
    elif aku_type not in VALID_TYPES:
        err(f"'type' должен быть одним из {VALID_TYPES}, получено: '{aku_type}'")

    # --- STRENGTH ---
    strength = data.get("strength")
    if not strength:
        err("Отсутствует поле 'strength'")
    elif strength not in VALID_STRENGTHS:
        err(f"'strength' должен быть одним из {VALID_STRENGTHS}, получено: '{strength}'")

    # --- STATUS ---
    status = data.get("status")
    if not status:
        err("Отсутствует поле 'status'")
    elif status not in VALID_STATUSES:
        err(f"'status' должен быть одним из {VALID_STATUSES}, получено: '{status}'")

    # --- TOPIC ---
    topic = data.get("topic")
    if not topic:
        err("Отсутствует поле 'topic'")
    elif topic not in taxonomy:
        err(f"'topic' = '{topic}' не найден в taxonomy.yaml. Добавь или исправь.")

    subtopics = data.get("subtopics") or []
    for st in subtopics:
        if st not in taxonomy:
            err(f"'subtopics' содержит '{st}' — не найден в taxonomy.yaml")

    # --- STATEMENT ---
    if not data.get("statement_ru"):
        err("Отсутствует 'statement_ru'")

    # --- SOURCE ---
    source = data.get("source") or {}
    if not source:
        err("Отсутствует блок 'source'")
    else:
        book_id = source.get("book_id")
        if not book_id:
            err("Отсутствует 'source.book_id'")
        elif book_id not in book_ids:
            err(f"'source.book_id' = '{book_id}' не найден в books.yaml")

        if not source.get("page"):
            err("Отсутствует 'source.page'")

        # Для verified — цитата обязательна
        if status == "verified":
            quote = source.get("verbatim_quote") or {}
            if not quote or not quote.get("text"):
                err("AKU со status=verified ОБЯЗАН иметь source.verbatim_quote.text")

    # --- FORMALIZATION ---
    form = data.get("formalization") or {}
    form_status = form.get("status", "not_attempted")
    if form_status not in VALID_FORM_STATUSES:
        err(f"'formalization.status' должен быть одним из {VALID_FORM_STATUSES}")

    # Если тип rule но формализация не попытана — предупреждение
    if aku_type == "rule" and strength == "mandatory" and form_status == "not_attempted":
        if status == "verified":
            warn("mandatory rule верифицирован, но формализация не попытана")

    # --- CREATED_BY ---
    created_by = data.get("created_by")
    if not created_by:
        err("Отсутствует 'created_by'")
    elif created_by not in VALID_CREATED_BY:
        err(f"'created_by' должен быть одним из {VALID_CREATED_BY}")

    if not data.get("created_at"):
        err("Отсутствует 'created_at'")

    # --- СВЯЗИ (orphan check) ---
    for field in ["related_aku", "contradicts_aku"]:
        refs = data.get(field) or []
        for ref in refs:
            if ref not in all_ids and ref != aku_id:
                warn(f"'{field}' содержит '{ref}' — AKU не найден в базе")

    for field in ["extends_aku", "supersedes_aku"]:
        ref = data.get(field)
        if ref and ref not in all_ids:
            warn(f"'{field}' = '{ref}' — AKU не найден в базе")

    return errors, warnings


# ============================================================
# ПРОВЕРКА УНИКАЛЬНОСТИ ID
# ============================================================

def check_id_uniqueness(aku_files):
    id_map = {}
    duplicates = []

    for filepath in aku_files:
        try:
            data = load_yaml(filepath)
            if isinstance(data, dict) and "id" in data:
                aku_id = data["id"]
                if aku_id in id_map:
                    duplicates.append((aku_id, id_map[aku_id], filepath))
                else:
                    id_map[aku_id] = filepath
        except Exception as e:
            pass

    return duplicates


# ============================================================
# MAIN
# ============================================================

def collect_files(path_arg=None):
    if path_arg:
        target = Path(path_arg)
        if target.is_file() and target.suffix == ".yaml":
            return [target]
        elif target.is_dir():
            return list(target.rglob("*.yaml"))
        else:
            print(f"Путь не найден: {path_arg}")
            sys.exit(1)
    else:
        return list(AKU_DIR.rglob("*.yaml"))


def main():
    path_arg = sys.argv[1] if len(sys.argv) > 1 else None
    aku_files = collect_files(path_arg)

    if not aku_files:
        print("AKU файлы не найдены.")
        sys.exit(0)

    # Загрузка конфигурации
    try:
        taxonomy = load_taxonomy()
        book_ids = load_book_ids()
        all_ids = load_all_aku_ids()
    except FileNotFoundError as e:
        print(f"❌ Не найден файл конфигурации: {e}")
        print("   Убедись что запускаешь из корня проекта.")
        sys.exit(1)

    # Проверка уникальности ID
    duplicates = check_id_uniqueness(aku_files)

    total = 0
    passed = 0
    failed = 0
    warned = 0

    print(f"\n{'='*60}")
    print(f"  Elliott Wave Brain — AKU Validator")
    print(f"  Файлов для проверки: {len(aku_files)}")
    print(f"{'='*60}\n")

    # Дубликаты
    if duplicates:
        print("❌ ДУБЛИКАТЫ ID:")
        for aku_id, path1, path2 in duplicates:
            print(f"  {aku_id}: {path1} ↔ {path2}")
        print()

    # Валидация каждого файла
    for filepath in sorted(aku_files):
        total += 1
        try:
            data = load_yaml(filepath)
            if not isinstance(data, dict):
                print(f"❌ {filepath.name}: не является YAML-словарём")
                failed += 1
                continue

            errors, warnings = validate_aku(data, filepath, taxonomy, book_ids, all_ids)

            if errors:
                failed += 1
                print(f"❌ {filepath.name} [{data.get('id', '?')}]")
                for e in errors:
                    print(e)
                if warnings:
                    for w in warnings:
                        print(w)
                print()
            elif warnings:
                warned += 1
                passed += 1
                print(f"⚠️  {filepath.name} [{data.get('id', '?')}] — прошёл с предупреждениями")
                for w in warnings:
                    print(w)
                print()
            else:
                passed += 1
                print(f"✅ {filepath.name} [{data.get('id', '?')}]")

        except yaml.YAMLError as e:
            failed += 1
            print(f"❌ {filepath.name}: ошибка YAML — {e}\n")
        except Exception as e:
            failed += 1
            print(f"❌ {filepath.name}: неожиданная ошибка — {e}\n")

    # Итог
    print(f"\n{'='*60}")
    print(f"  Итого: {total} файлов")
    print(f"  ✅ Прошли: {passed}  |  ❌ Упали: {failed}  |  ⚠️  С предупреждениями: {warned}")
    print(f"{'='*60}\n")

    sys.exit(1 if failed > 0 or duplicates else 0)


if __name__ == "__main__":
    main()
