"""Build Probability Calibration v0 artifacts for indicator signals."""
from __future__ import annotations

import json
import os
import sys
import argparse
from datetime import datetime, timezone

import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ewb.research import build_probability_calibration


REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SOURCE = os.path.join(REPO, "python", "data", "trades_sprint6.parquet")
OUT_DIR = os.path.join(REPO, "brain-output", "indicator-spec")

SIGNAL_ID_COLUMNS = ["ticker", "interval", "fig_type", "side", "confirm_idx", "entry_ts"]


def output_paths(asset_class: str) -> tuple[str, str]:
    suffix = "_crypto" if asset_class == "crypto" else ""
    return (
        os.path.join(OUT_DIR, f"probability_calibration{suffix}_v0.json"),
        os.path.join(OUT_DIR, f"probability_calibration{suffix}_v0.md"),
    )


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


def canonical_trade_records(trades: pd.DataFrame, asset_class: str) -> tuple[pd.DataFrame, dict]:
    """Select one execution variant per signal before probability calibration.

    Historical grid files intentionally contain many entry/TP/SL/MTF variants.
    Calibration must not count those variants as independent observations.
    """
    out = trades.copy()
    source_rows = len(out)
    filters: list[str] = []

    if "mtf_policy" in out.columns:
        none_mtf = out[out["mtf_policy"] == "none"]
        if not none_mtf.empty:
            out = none_mtf.copy()
            filters.append("mtf_policy=none")

    if "entry_variant" in out.columns:
        preferred_entries = (
            ["next_bar_open", "next_open", "confirm_close"]
            if asset_class == "crypto"
            else ["next_open", "confirm_close", "next_bar_open"]
        )
        for entry_variant in preferred_entries:
            entry_rows = out[out["entry_variant"] == entry_variant]
            if not entry_rows.empty:
                out = entry_rows.copy()
                filters.append(f"entry_variant={entry_variant}")
                break

    numeric_filters = {
        "tp_mult": 1.0,
        "sl_mult": 1.0,
    }
    for col, value in numeric_filters.items():
        if col in out.columns:
            rows = out[np.isclose(out[col].astype(float), value)]
            if not rows.empty:
                out = rows.copy()
                filters.append(f"{col}={value}")

    if "exit_plan" in out.columns:
        rows = out[out["exit_plan"] == "full"]
        if not rows.empty:
            out = rows.copy()
            filters.append("exit_plan=full")

    signal_cols = [col for col in SIGNAL_ID_COLUMNS if col in out.columns]
    if signal_cols:
        out = out.sort_values(["entry_ts", "ticker"] if "ticker" in out.columns else ["entry_ts"])
        out = out.drop_duplicates(signal_cols, keep="first")
        filters.append("unique_signal_id=" + "+".join(signal_cols))

    meta = {
        "source_rows": int(source_rows),
        "canonical_rows": int(len(out)),
        "canonical_filters": filters,
        "signal_id_columns": signal_cols,
    }
    return out, meta


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


def write_markdown(payload: dict, md_out: str) -> None:
    generated_at = payload["generated_at"]
    asset_class = payload.get("asset_class", "stocks")
    source = payload.get("source", SOURCE)
    lines = [
        f"# Probability Calibration v0 — {asset_class}",
        "",
        f"Generated: `{generated_at}`",
        "",
        "Purpose: machine-readable calibration for indicator output fields `p_up`, `p_down`, `p_trade_win`, `expected_net_return`, `confidence` and `recommended_action`.",
        "",
        f"Asset class: `{asset_class}`.",
        f"Source: `{source}`.",
        "",
        "Important: do not mix this calibration with another asset class inside Pine.",
        "",
        "Lookup priority:",
        "",
    ]
    for item in payload["lookup_priority"]:
        lines.append(f"- `{item}`")

    for level in payload["lookup_priority"]:
        lines.extend(["", f"## {level}", ""])
        lines.extend(md_table(rows_for_level(payload, level)))

    with open(md_out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset-class", choices=["stocks", "crypto"], default="stocks")
    parser.add_argument("--source", default=SOURCE)
    args = parser.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    json_out, md_out = output_paths(args.asset_class)
    trades = pd.read_parquet(args.source)
    trades, canonical_meta = canonical_trade_records(trades, args.asset_class)
    payload = build_probability_calibration(trades)
    payload["asset_class"] = args.asset_class
    payload["model_version"] = (
        "probability-calibration-crypto-v0"
        if args.asset_class == "crypto"
        else "probability-calibration-v0"
    )
    payload["source"] = args.source
    payload["source_rows"] = canonical_meta["source_rows"]
    payload["canonical_rows"] = canonical_meta["canonical_rows"]
    payload["canonical_filters"] = canonical_meta["canonical_filters"]
    payload["signal_id_columns"] = canonical_meta["signal_id_columns"]
    payload["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    write_markdown(payload, md_out)
    print(f"JSON: {json_out}")
    print(f"Markdown: {md_out}")
    print(f"Rows: {len(payload['rows'])}")


if __name__ == "__main__":
    main()
