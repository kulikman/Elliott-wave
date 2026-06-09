#!/usr/bin/env python3
"""
accept_review_queue.py — Принять все requires_review: true AKU как verified.

Использовать только после явного подтверждения владельца.
Устанавливает:
  requires_review: false
  status: verified  (если было draft)
  review_notes: "Reviewed and approved by Anton 2026-06-09"
"""
import sys
import yaml
import glob
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))
from tools._lib.aku_io import load_aku, save_aku
from tools._lib.log import info, ok, warn

TODAY = "2026-06-09"


def main() -> None:
    files = sorted(glob.glob("aku/**/*.yaml", recursive=True))
    changed = 0
    for fpath in files:
        if "/golden/" in fpath:
            continue
        path = Path(fpath)
        data = load_aku(path)
        if not data.get("requires_review", False):
            continue

        old_status = data.get("status", "draft")
        data["requires_review"] = False

        # Если статус draft → переводим в verified
        if old_status == "draft":
            data["status"] = "verified"

        # Обновляем review_notes
        existing = data.get("review_notes") or ""
        suffix = f"Reviewed and approved by Anton {TODAY}."
        if suffix not in existing:
            data["review_notes"] = (existing + "\n" + suffix).strip()

        save_aku(data, path)
        ok(f"  {data['id']:12}  {old_status} → verified")
        changed += 1

    info(f"\n✅ Принято: {changed} AKU")


if __name__ == "__main__":
    main()
