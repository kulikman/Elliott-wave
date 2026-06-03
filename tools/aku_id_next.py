#!/usr/bin/env python3
"""
AKU ID Generator
Elliott Wave Brain

Возвращает следующий доступный ID вида AKU-XXXX

Запуск:
  python tools/aku_id_next.py         → выводит: AKU-0042
  python tools/aku_id_next.py --peek  → только показывает, не резервирует
"""

import sys
import yaml
import re
from pathlib import Path

AKU_DIR = Path(__file__).parent.parent / "aku"
AKU_ID_PATTERN = re.compile(r"^AKU-(\d{4})$")


def get_all_ids():
    ids = set()
    for yaml_file in AKU_DIR.rglob("*.yaml"):
        try:
            with open(yaml_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if isinstance(data, dict) and "id" in data:
                match = AKU_ID_PATTERN.match(str(data["id"]))
                if match:
                    ids.add(int(match.group(1)))
        except Exception:
            pass
    return ids


def next_id():
    existing = get_all_ids()
    if not existing:
        return "AKU-0001"
    next_num = max(existing) + 1
    return f"AKU-{next_num:04d}"


if __name__ == "__main__":
    print(next_id())
