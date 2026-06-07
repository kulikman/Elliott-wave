"""Append and settle forward EWB bot-signal events.

The log is event-sourced JSONL on purpose: every alert/outcome is immutable,
easy to diff, and can be replayed into a trade table.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ewb.strategy_system import (
    DEFAULT_FORWARD_LOG,
    append_jsonl,
    forward_trades,
    outcome_event,
    read_jsonl,
    signal_event,
    signal_event_from_payload,
    trade_summary,
    write_frame,
)


REPO = Path(__file__).resolve().parents[2]


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--log", default=str(REPO / DEFAULT_FORWARD_LOG))
    sub = p.add_subparsers(dest="cmd", required=True)

    add = sub.add_parser("add", help="Append a new forward signal")
    add.add_argument("--ticker")
    add.add_argument("--interval")
    add.add_argument("--action", choices=["buy", "sell", "long", "short"])
    add.add_argument("--entry-ts")
    add.add_argument("--entry-px", type=float)
    add.add_argument("--stop-px", type=float)
    add.add_argument("--target-px", type=float)
    add.add_argument("--fig-type", default="unknown")
    add.add_argument("--probability", type=float)
    add.add_argument("--htf-context", default="")
    add.add_argument("--signal-id")
    add.add_argument("--source", default="manual")
    add.add_argument("--event-json", help="Optional JSON object with the same fields")

    settle = sub.add_parser("settle", help="Append an outcome for an existing signal")
    settle.add_argument("--signal-id", required=True)
    settle.add_argument("--exit-ts", required=True)
    settle.add_argument("--exit-px", required=True, type=float)
    settle.add_argument("--exit-reason", required=True, choices=["tp", "sl", "time", "manual", "cancelled"])

    sub.add_parser("summary", help="Print current forward-log summary")
    return p


def add_event(args: argparse.Namespace) -> dict:
    if args.event_json:
        payload = json.loads(args.event_json)
        row = signal_event_from_payload(payload, source=args.source)
        append_jsonl(Path(args.log), row)
        return row

    missing = [
        name
        for name, value in {
            "--ticker": args.ticker,
            "--interval": args.interval,
            "--action": args.action,
            "--entry-ts": args.entry_ts,
            "--entry-px": args.entry_px,
        }.items()
        if value in (None, "")
    ]
    if missing:
        raise SystemExit("Missing required arguments for manual add: " + ", ".join(missing))

    row = signal_event(
        ticker=args.ticker,
        interval=args.interval,
        action=args.action,
        entry_ts=args.entry_ts,
        entry_px=args.entry_px,
        stop_px=args.stop_px,
        target_px=args.target_px,
        fig_type=args.fig_type,
        probability=args.probability,
        htf_context=args.htf_context,
        signal_id=args.signal_id,
        source=args.source,
    )
    append_jsonl(Path(args.log), row)
    return row


def settle_event(args: argparse.Namespace) -> dict:
    row = outcome_event(
        signal_id=args.signal_id,
        exit_ts=args.exit_ts,
        exit_px=args.exit_px,
        exit_reason=args.exit_reason,
    )
    append_jsonl(Path(args.log), row)
    return row


def print_summary(path: Path) -> None:
    trades = forward_trades(read_jsonl(path))
    out_path = write_frame(trades, path.with_suffix(".parquet"))
    closed = trades[trades["status"] == "closed"] if not trades.empty else trades
    summary = trade_summary(closed)
    print(f"Log: {path}")
    print(f"Export: {out_path}")
    print(f"Signals: {len(trades)}")
    print(f"Closed: {len(closed)}")
    if summary.get("trades", 0):
        print(
            "Closed metrics: "
            f"winrate={summary['winrate']:.1%}, "
            f"expectancy={summary['expectancy']:.2%}, "
            f"PF={summary['profit_factor']:.2f}, "
            f"DD={summary['max_drawdown']:.1%}"
        )


def main() -> None:
    args = parser().parse_args()
    path = Path(args.log)
    if args.cmd == "add":
        row = add_event(args)
        print(f"Added signal {row['signal_id']}")
    elif args.cmd == "settle":
        row = settle_event(args)
        print(f"Settled signal {row['signal_id']}")
    elif args.cmd == "summary":
        print_summary(path)


if __name__ == "__main__":
    main()
