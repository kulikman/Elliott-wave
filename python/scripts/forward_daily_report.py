"""Build Anton's daily forward-trading control report."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ewb.strategy_system import (
    DEFAULT_BACKTEST_DIR,
    DEFAULT_FORWARD_LOG,
    forward_trades,
    markdown_table,
    read_jsonl,
    trade_summary,
    write_frame,
    write_json,
)


REPO = Path(__file__).resolve().parents[2]


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--forward-log", default=str(REPO / DEFAULT_FORWARD_LOG))
    p.add_argument(
        "--backtest-summary",
        default=str(REPO / DEFAULT_BACKTEST_DIR / "ewb_strategy_backtest_summary.json"),
    )
    p.add_argument("--output-dir", default=str(REPO / DEFAULT_BACKTEST_DIR))
    p.add_argument("--max-open", type=int, default=30)
    p.add_argument("--max-closed", type=int, default=30)
    return p


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def fmt_price(value: Any) -> str:
    if value in (None, "") or pd.isna(value):
        return "n/a"
    try:
        return f"{float(value):.4g}"
    except Exception:
        return str(value)


def pct_text(value: Any) -> str:
    if value in (None, "") or pd.isna(value):
        return "n/a"
    return f"{float(value) * 100:.1f}%"


def bot_decision(closed_count: int, summary: dict[str, Any]) -> tuple[str, str]:
    if closed_count < 30:
        return "OBSERVE", "Меньше 30 закрытых forward-сделок. Реальные деньги и автоматизацию не включать."
    expectancy = summary.get("expectancy")
    profit_factor = summary.get("profit_factor")
    if expectancy is not None and pd.notna(expectancy) and float(expectancy) < 0:
        return "BLOCK", "Forward expectancy ниже 0. Нужен аудит сигналов и исполнения."
    if profit_factor is not None and pd.notna(profit_factor) and float(profit_factor) < 1.1:
        return "BLOCK", "Forward profit factor ниже 1.1. Риск/выходы не подтверждены."
    if closed_count < 100:
        return "PAPER ONLY", "30-99 закрытых сделок: можно оценивать стабильность, но не масштабировать риск."
    return "READY TO REVIEW", "100+ сделок: можно решать по сравнению forward с baseline и просадке."


def rows_for_open(open_trades: pd.DataFrame, limit: int) -> list[dict[str, Any]]:
    if open_trades.empty:
        return []
    scoped = open_trades.sort_values("entry_ts", ascending=False).head(limit)
    rows = []
    for _, row in scoped.iterrows():
        rows.append({
            "signal_id": row.get("signal_id", ""),
            "ticker": row.get("ticker", ""),
            "tf": row.get("interval", ""),
            "side": row.get("side", ""),
            "pattern": row.get("fig_type", ""),
            "entry": fmt_price(row.get("entry_px")),
            "stop": fmt_price(row.get("stop_px")),
            "target": fmt_price(row.get("target_px")),
            "p": row.get("probability"),
            "time": row.get("entry_ts"),
        })
    return rows


def rows_for_closed(closed: pd.DataFrame, limit: int) -> list[dict[str, Any]]:
    if closed.empty:
        return []
    scoped = closed.sort_values("exit_ts", ascending=False).head(limit)
    rows = []
    for _, row in scoped.iterrows():
        rows.append({
            "ticker": row.get("ticker", ""),
            "tf": row.get("interval", ""),
            "side": row.get("side", ""),
            "pattern": row.get("fig_type", ""),
            "entry": fmt_price(row.get("entry_px")),
            "exit": fmt_price(row.get("exit_px")),
            "ret": pct_text(row.get("net_ret")),
            "reason": row.get("exit_reason", ""),
            "exit_ts": row.get("exit_ts"),
        })
    return rows


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    metric_rows = [
        {"scope": "Historical baseline", **payload["historical"]},
        {"scope": "Forward closed", **payload["forward"]},
    ]
    metric_cols = [
        ("Scope", "scope"), ("Trades", "trades"), ("Win", "winrate"),
        ("Exp", "expectancy"), ("PF", "profit_factor"), ("DD", "max_drawdown"),
    ]
    open_cols = [
        ("ID", "signal_id"), ("Ticker", "ticker"), ("TF", "tf"), ("Side", "side"),
        ("Pattern", "pattern"), ("Entry", "entry"), ("SL", "stop"),
        ("TP", "target"), ("P", "p"), ("Time", "time"),
    ]
    closed_cols = [
        ("Ticker", "ticker"), ("TF", "tf"), ("Side", "side"), ("Pattern", "pattern"),
        ("Entry", "entry"), ("Exit", "exit"), ("Ret", "ret"),
        ("Reason", "reason"), ("Exit time", "exit_ts"),
    ]
    lines = [
        "# EWB Forward Daily Report",
        "",
        f"Decision: **{payload['decision']}**",
        "",
        payload["decision_reason"],
        "",
        "## Metrics",
        "",
        markdown_table(metric_rows, metric_cols, limit=2),
        "",
        "## Open Trades",
        "",
    ]
    if payload["open_rows"]:
        lines.append(markdown_table(payload["open_rows"], open_cols, limit=len(payload["open_rows"])))
    else:
        lines.append("No open forward trades.")
    lines.extend(["", "## Recently Closed", ""])
    if payload["closed_rows"]:
        lines.append(markdown_table(payload["closed_rows"], closed_cols, limit=len(payload["closed_rows"])))
    else:
        lines.append("No closed forward trades.")
    lines.extend([
        "",
        "## Operating Rule",
        "",
        "- Пока decision = OBSERVE или PAPER ONLY, сделки используются только для статистики.",
        "- Если появляется BLOCK, остановить новые входы и проверить repaint, цену исполнения, HTF context и SL/TP.",
        "- Масштабировать риск можно только после стабильного forward-подтверждения, а не по historical baseline.",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parser().parse_args()
    output_dir = Path(args.output_dir)
    events = read_jsonl(Path(args.forward_log))
    trades = forward_trades(events)
    open_trades = trades[trades["status"] == "open"].copy() if not trades.empty else pd.DataFrame()
    closed = trades[trades["status"] == "closed"].copy() if not trades.empty else pd.DataFrame()
    forward_summary = trade_summary(closed.sort_values("entry_ts") if not closed.empty else closed)

    backtest_summary = load_json(Path(args.backtest_summary))
    historical_summary = backtest_summary.get("portfolio", {})
    decision, decision_reason = bot_decision(len(closed), forward_summary)

    forward_path = write_frame(trades, output_dir / "ewb_forward_daily_trades.parquet")
    payload = {
        "decision": decision,
        "decision_reason": decision_reason,
        "counts": {
            "events": len(events),
            "signals": int(len(trades)),
            "open": int(len(open_trades)),
            "closed": int(len(closed)),
        },
        "historical": historical_summary,
        "forward": forward_summary,
        "open_rows": rows_for_open(open_trades, args.max_open),
        "closed_rows": rows_for_closed(closed, args.max_closed),
        "outputs": {
            "trades": str(forward_path),
            "markdown": str(output_dir / "ewb_forward_daily_report.md"),
            "json": str(output_dir / "ewb_forward_daily_report.json"),
        },
    }
    write_json(output_dir / "ewb_forward_daily_report.json", payload)
    write_markdown(output_dir / "ewb_forward_daily_report.md", payload)
    print(f"Wrote {payload['outputs']['markdown']}")
    print(json.dumps(payload["counts"], indent=2))
    print(f"Decision: {decision}")


if __name__ == "__main__":
    main()
