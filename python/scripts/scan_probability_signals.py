"""Scan tickers and emit Probability Model v0 signals from matched figures."""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ewb.figures import match_figures
from ewb.monowaves import detect_monowaves
from ewb.rules import classify_pivots
from ewb.wave3 import detect_wave3_setups
from ewb.research import (
    download_ohlc,
    load_probability_calibration,
    log_processing_error,
    probability_signal_from_figure,
)


REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_CALIBRATION = os.path.join(
    REPO,
    "brain-output",
    "indicator-spec",
    "probability_calibration_v0.json",
)
DEFAULT_OUTPUT_DIR = os.path.join(REPO, "brain-output", "signals")
DEFAULT_PERIODS = {
    "1d": "5y",
    "1h": "730d",
    "4h": "730d",   # resampled from 1h (yfinance 1h max ~730d)
    "30m": "60d",
    "15m": "60d",
    "1w": "10y",    # alias of 1wk
    "1wk": "10y",
}


def pct(value: float | None, digits: int = 1) -> str:
    number = finite_number(value)
    if number is None:
        return "n/a"
    return f"{number * 100:.{digits}f}%"


def money_pct(value: float | None) -> str:
    number = finite_number(value)
    if number is None:
        return "n/a"
    sign = "+" if number >= 0 else ""
    return f"{sign}{number * 100:.2f}%"


def fmt_px(value: float | None) -> str:
    number = finite_number(value)
    if number is None:
        return "n/a"
    return f"{number:.2f}"


def finite_number(value: float | None) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tickers", required=True, help="Comma-separated tickers, e.g. AAPL,MSFT")
    p.add_argument("--interval", default="1h", help="yfinance interval, e.g. 1h or 1d")
    p.add_argument("--period", default=None, help="yfinance period; default depends on interval")
    p.add_argument("--limit", type=int, default=10, help="Max signals to print")
    p.add_argument(
        "--actions",
        default="buy,sell,skip",
        help="Comma-separated actions to include: buy,sell,wait,skip",
    )
    p.add_argument("--calibration", default=DEFAULT_CALIBRATION, help="Calibration JSON path")
    p.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Directory for saved outputs")
    p.add_argument("--save", action="store_true", help="Save JSON and Markdown outputs")
    p.add_argument("--fresh-hours", type=float, default=None, help="Keep signals from the last N hours")
    p.add_argument("--fresh-days", type=float, default=None, help="Keep signals from the last N days")
    return p


_WAVE3_WR_CACHE: dict | None = None


def _wave3_winrates() -> dict:
    """Load backtested W3 winrates: (asset_class, interval, side) -> (wr, n)."""
    global _WAVE3_WR_CACHE
    if _WAVE3_WR_CACHE is not None:
        return _WAVE3_WR_CACHE
    import pandas as pd
    from pathlib import Path
    f = Path(__file__).resolve().parents[2] / "brain-output" / "backtests" / "ewb_wave3_backtest_grouped.parquet"
    lut: dict = {}
    if f.exists():
        try:
            g = pd.read_parquet(f)
            for _, r in g.iterrows():
                lut[(str(r["asset_class"]), str(r["interval"]), str(r["side"]))] = (
                    float(r["winrate"]), int(r["trades"]))
        except Exception:
            pass
    _WAVE3_WR_CACHE = lut
    return lut


def scan_ticker(ticker: str, interval: str, period: str, calibration: dict) -> list[dict]:
    df = download_ohlc(ticker, interval, period, min_rows=100)
    if df is None:
        return []
    pivots = detect_monowaves(df, atr_mult=2.5)
    classify_pivots(pivots)
    figures = match_figures(pivots)
    signals = []
    for figure in figures:
        if not figure.confirmed:
            continue
        signal = probability_signal_from_figure(calibration, figure, df, ticker, interval)
        if signal is not None:
            signals.append(signal)

    # EPIC 3: Wave-3 trend entries. Validated by backtest_wave3.py; each W3
    # signal carries p_trade_win = its backtested group winrate so the
    # auto-trader's MIN_P_WIN + winrate gate both apply (stock-long/crypto-short
    # pass at 59%, stock-short/crypto-long fall below the floor).
    if os.getenv("EWB_WAVE3") == "1":
        last_idx = len(df) - 1
        last_px = float(df["close"].iloc[last_idx])
        last_ts = str(df.index[last_idx])
        w3_wr = _wave3_winrates()
        asset = "crypto" if str(ticker).upper().endswith("-USD") else "stock"
        # Many past W1/W2 triples can still be "triggered"; keep only the
        # freshest setup per side (largest entry_idx) to avoid flooding.
        freshest: dict[str, object] = {}
        for setup in detect_wave3_setups(pivots, last_px, last_idx):
            if not (setup.triggered and setup.struct_ok and setup.rr1 >= 1.0):
                continue
            cur = freshest.get(setup.side)
            if cur is None or setup.entry_idx > cur.entry_idx:
                freshest[setup.side] = setup
        for setup in freshest.values():
            sig = setup.to_signal(ticker, interval, last_ts)
            wr, n = w3_wr.get((asset, interval, setup.side), (0.0, 0))
            sig["p_trade_win"] = wr
            sig["sample_size"] = n
            signals.append(sig)
    return signals


def parse_signal_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        ts = datetime.fromisoformat(value)
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def freshness_delta(fresh_hours: float | None = None, fresh_days: float | None = None) -> timedelta | None:
    if fresh_hours is not None:
        return timedelta(hours=fresh_hours)
    if fresh_days is not None:
        return timedelta(days=fresh_days)
    return None


def filter_fresh_signals(
    signals: list[dict],
    fresh_hours: float | None = None,
    fresh_days: float | None = None,
    now: datetime | None = None,
) -> list[dict]:
    delta = freshness_delta(fresh_hours=fresh_hours, fresh_days=fresh_days)
    if delta is None:
        return signals
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    cutoff = now - delta
    fresh = []
    for signal in signals:
        entry_ts = parse_signal_ts(signal.get("entry_ts"))
        if entry_ts is not None and entry_ts.astimezone(timezone.utc) >= cutoff.astimezone(timezone.utc):
            fresh.append(signal)
    return fresh


def freshness_label(fresh_hours: float | None = None, fresh_days: float | None = None) -> str | None:
    if fresh_hours is not None:
        return f"{fresh_hours:g}h"
    if fresh_days is not None:
        return f"{fresh_days:g}d"
    return None


def output_basename(interval: str, actions: set[str], freshness: str | None = None) -> str:
    action_part = "-".join(sorted(actions))
    suffix = f"_fresh-{freshness}" if freshness else ""
    return f"probability_signals_{interval}_{action_part}{suffix}"


def build_payload(
    signals: list[dict],
    tickers: list[str],
    interval: str,
    period: str,
    actions: set[str],
    limit: int,
    calibration: dict,
    fresh_hours: float | None = None,
    fresh_days: float | None = None,
) -> dict:
    freshness = freshness_label(fresh_hours=fresh_hours, fresh_days=fresh_days)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model_version": calibration.get("model_version", "unknown"),
        "tickers": tickers,
        "interval": interval,
        "period": period,
        "actions": sorted(actions),
        "freshness": freshness,
        "fresh_hours": fresh_hours,
        "fresh_days": fresh_days,
        "limit": limit,
        "n_signals": len(signals),
        "signals": signals,
    }


def markdown_report(payload: dict) -> str:
    lines = [
        "# Probability Signals",
        "",
        f"Generated: `{payload['generated_at']}`",
        f"Model: `{payload['model_version']}`",
        f"Tickers: `{', '.join(payload['tickers'])}`",
        f"Interval: `{payload['interval']}`",
        f"Actions: `{', '.join(payload['actions'])}`",
        f"Freshness: `{payload['freshness'] or 'all'}`",
        f"Signals: `{payload['n_signals']}`",
        "",
        "| ticker | action | pattern | entry_ts | P(win) | EV | conf | entry | stop | target |",
        "|---|---|---|---|---:|---:|---|---:|---:|---:|",
    ]
    for signal in payload["signals"]:
        risk = signal.get("risk_box", {})
        lines.append(
            f"| {signal.get('ticker')} | {signal.get('recommended_action')} | "
            f"{signal.get('pattern')} | {signal.get('entry_ts')} | "
            f"{pct(signal.get('p_trade_win'))} | {money_pct(signal.get('expected_net_return'))} | "
            f"{signal.get('confidence')} | {fmt_px(risk.get('entry_px'))} | "
            f"{fmt_px(risk.get('stop_px'))} | {fmt_px(risk.get('target_px'))} |"
        )
    return "\n".join(lines) + "\n"


def save_outputs(payload: dict, output_dir: str) -> tuple[str, str]:
    os.makedirs(output_dir, exist_ok=True)
    base = output_basename(payload["interval"], set(payload["actions"]), payload.get("freshness"))
    json_path = os.path.join(output_dir, f"{base}.json")
    md_path = os.path.join(output_dir, f"{base}.md")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown_report(payload))
    return json_path, md_path


def main() -> None:
    args = parser().parse_args()
    tickers = [ticker.strip().upper() for ticker in args.tickers.split(",") if ticker.strip()]
    actions = {action.strip() for action in args.actions.split(",") if action.strip()}
    period = args.period or DEFAULT_PERIODS.get(args.interval, "730d")
    calibration = load_probability_calibration(args.calibration)
    all_signals: list[dict] = []

    for ticker in tickers:
        try:
            all_signals.extend(scan_ticker(ticker, args.interval, period, calibration))
        except Exception as exc:
            log_processing_error(ticker, args.interval, exc, context="probability_scan")

    filtered = [
        signal
        for signal in all_signals
        if signal["recommended_action"] in actions
    ]
    filtered.sort(key=lambda signal: signal.get("entry_ts") or "", reverse=True)
    filtered = filter_fresh_signals(
        filtered,
        fresh_hours=args.fresh_hours,
        fresh_days=args.fresh_days,
    )
    payload = build_payload(
        filtered[:args.limit],
        tickers=tickers,
        interval=args.interval,
        period=period,
        actions=actions,
        limit=args.limit,
        calibration=calibration,
        fresh_hours=args.fresh_hours,
        fresh_days=args.fresh_days,
    )
    if args.save:
        json_path, md_path = save_outputs(payload, args.output_dir)
        print(f"JSON: {json_path}")
        print(f"Markdown: {md_path}")
    else:
        print(json.dumps(payload["signals"], ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
