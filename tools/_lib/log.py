"""Structured logging на русском для терминала."""

import sys
from datetime import datetime


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def info(msg: str) -> None:
    print(f"[{_ts()}] ℹ️  {msg}", file=sys.stdout)


def ok(msg: str) -> None:
    print(f"[{_ts()}] ✅ {msg}", file=sys.stdout)


def warn(msg: str) -> None:
    print(f"[{_ts()}] ⚠️  {msg}", file=sys.stderr)


def error(msg: str) -> None:
    print(f"[{_ts()}] ❌ {msg}", file=sys.stderr)


def step(msg: str) -> None:
    print(f"\n[{_ts()}] 🔹 {msg}", file=sys.stdout)


def section(title: str) -> None:
    line = "─" * 60
    print(f"\n{line}\n  {title}\n{line}", file=sys.stdout)


def progress(current: int, total: int, label: str = "") -> None:
    pct = int(current / total * 100) if total else 0
    bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
    suffix = f" {label}" if label else ""
    print(f"\r  [{bar}] {pct}% ({current}/{total}){suffix}", end="", flush=True)
    if current >= total:
        print()
