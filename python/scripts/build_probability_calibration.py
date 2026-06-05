"""Build Probability Calibration v0 artifacts for indicator signals."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ewb.research import build_probability_calibration


REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SOURCE = os.path.join(REPO, "python", "data", "trades_sprint6.parquet")
OUT_DIR = os.path.join(REPO, "brain-output", "indicator-spec")
JSON_OUT = os.path.join(OUT_DIR, "probability_calibration_v0.json")
MD_OUT = os.path.join(OUT_DIR, "probability_calibration_v0.md")


def pct(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.{digits}f}%"


def money_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value * 100:.2f}%"


def rows_for_level(payload: dict, level: str) -> list[dict]:
    return [row for row in payload["rows"] if row["level"] == level]


def md_table(rows: list[dict]) -> list[str]:
    lines = [
        "| key | n | action | P(win) | P(up) | P(down) | EV | confidence |",
        "|---|---:|---|---:|---:|---:|---:|---|",
    ]
    for row in sorted(rows, key=lambda r: (str(r.get("fig_type")), str(r.get("interval")), str(r.get("side")))):
        lines.append(
            f"| `{row['key']}` | {row['n']} | {row['recommended_action']} | "
            f"{pct(row['p_trade_win'])} | {pct(row.get('p_up'))} | {pct(row.get('p_down'))} | "
            f"{money_pct(row['expected_net_return'])} | {row['confidence']} |"
        )
    return lines


def write_markdown(payload: dict) -> None:
    generated_at = payload["generated_at"]
    lines = [
        "# Probability Calibration v0",
        "",
        f"Generated: `{generated_at}`",
        "",
        "Purpose: machine-readable calibration for indicator output fields `p_up`, `p_down`, `p_trade_win`, `expected_net_return`, `confidence` and `recommended_action`.",
        "",
        "Source: `python/data/trades_sprint6.parquet`.",
        "",
        "Important: this file calibrates probabilities from the stored sprint6 trade records. Use `docs/validation/sprint6-final.md` as the final portfolio baseline.",
        "",
        "Lookup priority:",
        "",
    ]
    for item in payload["lookup_priority"]:
        lines.append(f"- `{item}`")

    for level in payload["lookup_priority"]:
        lines.extend(["", f"## {level}", ""])
        lines.extend(md_table(rows_for_level(payload, level)))

    with open(MD_OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    trades = pd.read_parquet(SOURCE)
    payload = build_probability_calibration(trades)
    payload["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    write_markdown(payload)
    print(f"JSON: {JSON_OUT}")
    print(f"Markdown: {MD_OUT}")
    print(f"Rows: {len(payload['rows'])}")


if __name__ == "__main__":
    main()
