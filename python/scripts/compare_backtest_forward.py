"""Compare forward EWB alert outcomes against the historical bot baseline."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ewb.strategy_system import (
    DEFAULT_BACKTEST_DIR,
    DEFAULT_FORWARD_LOG,
    forward_trades,
    grouped_summary,
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
        "--backtest-trades",
        default=str(REPO / DEFAULT_BACKTEST_DIR / "ewb_strategy_backtest_trades.parquet"),
    )
    p.add_argument("--output-dir", default=str(REPO / DEFAULT_BACKTEST_DIR))
    return p


def load_backtest(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def write_markdown(path: Path, payload: dict, forward_grouped: pd.DataFrame) -> None:
    portfolio_cols = [
        ("Scope", "scope"), ("Trades", "trades"), ("Win", "winrate"),
        ("Exp", "expectancy"), ("PF", "profit_factor"), ("DD", "max_drawdown"),
    ]
    grouped_cols = [
        ("TF", "interval"), ("Pattern", "fig_type"), ("Side", "side"),
        ("Trades", "trades"), ("Win", "winrate"), ("Exp", "expectancy"),
        ("PF", "profit_factor"), ("DD", "max_drawdown"),
    ]
    rows = [
        {"scope": "Historical baseline", **payload["historical"]},
        {"scope": "Forward closed", **payload["forward_closed"]},
    ]
    lines = [
        "# EWB Backtest vs Forward",
        "",
        "This report is the bot reality check. If forward metrics diverge from history, do not scale capital.",
        "",
        "## Portfolio Comparison",
        "",
        markdown_table(rows, portfolio_cols, limit=2),
        "",
        "## Forward Closed By Setup",
        "",
    ]
    if forward_grouped.empty:
        lines.append("No closed forward trades yet.")
    else:
        lines.append(markdown_table(forward_grouped.to_dict("records"), grouped_cols, limit=30))
    lines.extend([
        "",
        "## Decision Rule",
        "",
        "- Fewer than 30 closed forward trades: observe only.",
        "- Forward expectancy below 0 or profit factor below 1.1: do not automate live size.",
        "- Big gap between historical and forward winrate: audit alerts, fill prices, repaint and HTF context.",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parser().parse_args()
    output_dir = Path(args.output_dir)
    historical = load_backtest(Path(args.backtest_trades))
    forward = forward_trades(read_jsonl(Path(args.forward_log)))
    closed = forward[forward["status"] == "closed"].copy() if not forward.empty else pd.DataFrame()

    historical_summary = trade_summary(historical.sort_values("entry_ts") if not historical.empty else historical)
    forward_summary = trade_summary(closed.sort_values("entry_ts") if not closed.empty else closed)
    forward_grouped = (
        grouped_summary(closed, ["interval", "fig_type", "side"])
        if not closed.empty else pd.DataFrame()
    )
    forward_path = write_frame(forward, output_dir / "ewb_forward_trades.parquet")
    grouped_path = write_frame(forward_grouped, output_dir / "ewb_forward_grouped.parquet")
    payload = {
        "historical": historical_summary,
        "forward_closed": forward_summary,
        "counts": {
            "historical_trades": int(len(historical)),
            "forward_signals": int(len(forward)),
            "forward_closed": int(len(closed)),
        },
        "outputs": {
            "forward_trades": str(forward_path),
            "forward_grouped": str(grouped_path),
            "markdown": str(output_dir / "ewb_backtest_vs_forward.md"),
            "json": str(output_dir / "ewb_backtest_vs_forward.json"),
        },
    }
    write_json(output_dir / "ewb_backtest_vs_forward.json", payload)
    write_markdown(output_dir / "ewb_backtest_vs_forward.md", payload, forward_grouped)
    print(f"Wrote {payload['outputs']['markdown']}")
    print(json.dumps(payload["counts"], indent=2))


if __name__ == "__main__":
    main()
