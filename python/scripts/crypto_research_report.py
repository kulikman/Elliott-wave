"""Build a crypto research-only report from the historical crypto signal grid."""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import datetime, timezone

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.scan_probability_signals import fmt_px, money_pct, pct


REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_TRADES = os.path.join(REPO, "python", "data", "historical_signal_grid_crypto_trades.parquet")
DEFAULT_OUTPUT_DIR = os.path.join(REPO, "brain-output", "signals")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--trades", default=DEFAULT_TRADES, help="Crypto historical grid parquet path")
    p.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Output directory")
    p.add_argument("--limit", type=int, default=30, help="Max rows in the report")
    return p


def pwin_fraction(value: float | None) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value) / 100.0


def finite_float(value: float | None) -> float | None:
    if value is None or pd.isna(value):
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def trade_level(row: pd.Series, level: str) -> float | None:
    entry = row.get("entry_px")
    amp_pct = row.get("amp_pct")
    if entry is None or amp_pct is None or pd.isna(entry) or pd.isna(amp_pct):
        return None
    amp = float(entry) * float(amp_pct)
    side = row.get("side")
    if level == "entry":
        return float(entry)
    if level == "target":
        mult = float(row.get("tp_mult", 1.0))
        return float(entry) + amp * mult if side == "long" else float(entry) - amp * mult
    if level == "stop":
        mult = float(row.get("sl_mult", 1.0))
        return float(entry) - amp * mult if side == "long" else float(entry) + amp * mult
    return None


def python_side(side: str) -> str:
    if side == "long":
        return "BUY"
    if side == "short":
        return "SELL"
    return "WAIT"


def research_rows(trades: pd.DataFrame, limit: int) -> list[dict]:
    filtered = trades[
        (trades["asset_class"] == "crypto")
        & (trades["entry_variant"] == "confirm_close")
        & (trades["mtf_policy"] == "none")
        & (trades["tp_mult"] == 1.0)
        & (trades["sl_mult"] == 1.0)
        & (trades["exit_plan"] == "full")
    ].copy()
    if filtered.empty:
        return []
    filtered["entry_ts_sort"] = pd.to_datetime(filtered["entry_ts"], utc=True, errors="coerce")
    filtered = filtered.sort_values(["entry_ts_sort", "ticker", "interval"], ascending=[False, True, True])
    filtered = filtered.groupby(["ticker", "interval"], as_index=False).head(1).head(limit)

    rows = []
    for _, row in filtered.iterrows():
        rows.append({
            "ticker": row.get("ticker"),
            "interval": row.get("interval"),
            "entry_ts": str(row.get("entry_ts")),
            "pattern": row.get("fig_type"),
            "python_side": python_side(str(row.get("side", ""))),
            "action_now": "WAIT",
            "reason": "CRYPTO_RESEARCH_ONLY",
            "model": "crypto-v0 research",
            "p_win": pwin_fraction(row.get("p_win_model")),
            "expected_net_return": finite_float(row.get("model_ev")),
            "confidence": row.get("confidence"),
            "sample_size": int(row.get("sample_size", 0)) if not pd.isna(row.get("sample_size")) else 0,
            "entry": finite_float(trade_level(row, "entry")),
            "stop": finite_float(trade_level(row, "stop")),
            "target": finite_float(trade_level(row, "target")),
            "exit_reason": row.get("exit_reason"),
            "net_return": finite_float(row.get("net_ret")),
        })
    return rows


def build_payload(trades: pd.DataFrame, limit: int) -> dict:
    rows = research_rows(trades, limit)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "asset_class": "crypto",
        "model_version": "probability-calibration-crypto-v0",
        "mode": "research-only",
        "action_contract": "WAIT unless crypto parity is explicitly promoted to production",
        "n_rows": len(rows),
        "rows": rows,
    }


def markdown_report(payload: dict) -> str:
    lines = [
        "# Crypto research report",
        "",
        f"Generated: `{payload['generated_at']}`",
        f"Asset class: `{payload['asset_class']}`",
        f"Model: `{payload['model_version']}`",
        f"Mode: `{payload['mode']}`",
        f"Rows: `{payload['n_rows']}`",
        "",
        "This report is intentionally research-only. It must not be used as BUY/SELL guidance",
        "until crypto Pine/Python parity and production calibration are approved.",
        "",
        "| ticker | TF | Python side | Action now | reason | pattern | P(win) | EV | conf / n | entry | stop | target |",
        "|---|---|---|---|---|---|---:|---:|---|---:|---:|---:|",
    ]
    if not payload["rows"]:
        lines.append("| n/a | n/a | n/a | WAIT | no crypto rows | n/a | n/a | n/a | n/a | n/a | n/a | n/a |")
    for row in payload["rows"]:
        lines.append(
            f"| {row['ticker']} | {row['interval']} | {row['python_side']} | "
            f"{row['action_now']} | {row['reason']} | {row['pattern']} | "
            f"{pct(row['p_win'])} | {money_pct(row['expected_net_return'])} | "
            f"{row['confidence']} / {row['sample_size']} | "
            f"{fmt_px(row['entry'])} | {fmt_px(row['stop'])} | {fmt_px(row['target'])} |"
        )
    lines.extend([
        "",
        "## Safety contract",
        "",
        "- Crypto rows are separated from the stock daily report.",
        "- Stock `probability_calibration_v0.json` is not used here.",
        "- `Action now` is always `WAIT` in this report.",
        "- Pine alerts must stay disabled for crypto until this report graduates from research.",
        "",
    ])
    return "\n".join(lines)


def save_outputs(payload: dict, output_dir: str) -> tuple[str, str]:
    os.makedirs(output_dir, exist_ok=True)
    json_path = os.path.join(output_dir, "crypto_research_report.json")
    md_path = os.path.join(output_dir, "crypto_research_report.md")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown_report(payload))
    return json_path, md_path


def main() -> None:
    args = parser().parse_args()
    trades = pd.read_parquet(args.trades)
    payload = build_payload(trades, args.limit)
    json_path, md_path = save_outputs(payload, args.output_dir)
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")


if __name__ == "__main__":
    main()
