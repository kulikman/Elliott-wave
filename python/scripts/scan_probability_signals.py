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


_CORE_WR_CACHE: dict | None = None


def _core_winrates() -> dict:
    """Load backtested core-setup winrates: (asset, interval, fig_type, side) -> (wr, n)."""
    global _CORE_WR_CACHE
    if _CORE_WR_CACHE is not None:
        return _CORE_WR_CACHE
    import pandas as pd
    from pathlib import Path
    f = Path(__file__).resolve().parents[2] / "brain-output" / "backtests" / "ewb_core_backtest_grouped.parquet"
    lut: dict = {}
    if f.exists():
        try:
            g = pd.read_parquet(f)
            for _, r in g.iterrows():
                lut[(str(r["asset_class"]), str(r["interval"]), str(r["fig_type"]), str(r["side"]))] = (
                    float(r["winrate"]), int(r["trades"]))
        except Exception:
            pass
    _CORE_WR_CACHE = lut
    return lut


def _emit_core_setups(ticker, interval, df, figures, signals):
    """Emit Neely core setups (triangle thrust, post-W4, etc.) as signals.

    Only the freshest figure per (setup, side) is emitted; p_trade_win/sample
    come from the core backtest LUT so the reward-first gate selects by
    expectancy (triangle thrust passes; thin/negative-EV setups are dropped)."""
    try:
        from scripts.neely_core_ab_backtest import neely_core_setups, entry_index
    except Exception:
        return
    core_wr = _core_winrates()
    asset = "crypto" if str(ticker).upper().endswith("-USD") else "stock"
    freshest: dict[tuple, dict] = {}
    for fig in figures:
        if not getattr(fig, "confirmed", False) or not getattr(fig, "pivots", None):
            continue
        e_idx = entry_index(fig)
        if e_idx < 0 or e_idx + 1 >= len(df):
            continue
        # next_open execution: enter at the OPEN of the bar after confirmation
        # (e_idx+1 is guaranteed to exist by the guard above).
        entry_px = float(df["open"].iloc[e_idx + 1])
        for s in neely_core_setups(fig):
            if "target" in s and "stop" in s:
                target, stop = float(s["target"]), float(s["stop"])
            elif "target_offset" in s:
                target = entry_px + float(s["target_offset"])
                stop = entry_px + float(s["stop_offset"])
            else:
                continue
            k = (s["setup"], s["side"])
            if k not in freshest or e_idx > freshest[k]["_eidx"]:
                freshest[k] = {"setup": s["setup"], "side": s["side"], "entry_px": entry_px,
                               "stop": stop, "target": target, "_eidx": e_idx,
                               "ts": str(df.index[e_idx + 1])}
    for v in freshest.values():
        wr, n = core_wr.get((asset, interval, v["setup"], v["side"]), (0.0, 0))
        signals.append({
            "pattern": v["setup"], "interval": interval, "ticker": ticker,
            "side": v["side"], "recommended_action": "buy" if v["side"] == "long" else "sell",
            "entry_ts": v["ts"], "confirmed": True,
            "risk_box": {"entry_px": v["entry_px"], "stop_px": v["stop"], "target_px": v["target"],
                         "amplitude": abs(v["target"] - v["entry_px"])},
            "p_trade_win": wr, "sample_size": n, "source": "core_engine",
        })


_HTFFLAT_WR_CACHE: dict | None = None
_HTF_RULE = {"1h": "4h", "4h": "1D"}


def _htf_flat_winrates() -> dict:
    global _HTFFLAT_WR_CACHE
    if _HTFFLAT_WR_CACHE is not None:
        return _HTFFLAT_WR_CACHE
    import pandas as pd
    from pathlib import Path
    f = Path(__file__).resolve().parents[2] / "brain-output" / "backtests" / "ewb_htf_flat_backtest_grouped.parquet"
    lut: dict = {}
    if f.exists():
        try:
            g = pd.read_parquet(f)
            for _, r in g.iterrows():
                lut[(str(r["asset_class"]), str(r["interval"]), str(r["side"]))] = (
                    float(r["winrate"]), int(r["trades"]))
        except Exception:
            pass
    _HTFFLAT_WR_CACHE = lut
    return lut


def _emit_htf_flat(ticker, interval, df, signals):
    """EPIC G: for LTF flat signals aligned with the higher-TF trend, emit a
    'flat_htf' variant carrying the HTF-aligned backtest winrate. EV-priority +
    sizing then favour it over the plain flat when the bigger wave agrees."""
    if interval not in _HTF_RULE:
        return
    try:
        from ewb.htf import htf_bias_series
        bias = htf_bias_series(df, _HTF_RULE[interval])
    except Exception:
        return
    wr_lut = _htf_flat_winrates()
    asset = "crypto" if str(ticker).upper().endswith("-USD") else "stock"
    extra = []
    for s in signals:
        if s.get("pattern") != "flat":
            continue
        side = s.get("side")
        ei = s.get("entry_idx")
        if ei is None or ei >= len(bias):
            continue
        b = int(bias.iloc[ei])
        if not ((side == "long" and b > 0) or (side == "short" and b < 0)):
            continue
        wr, n = wr_lut.get((asset, interval, side), (0.0, 0))
        if wr <= 0 or n <= 0:        # only validated HTF-aligned setups
            continue
        h = dict(s)
        h["pattern"] = "flat_htf"
        h["p_trade_win"] = wr
        h["sample_size"] = n
        h["source"] = "htf_flat"
        extra.append(h)
    signals.extend(extra)


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

    # EPIC G: HTF-aligned LTF flat variant (1h/4h flat in the higher-TF trend).
    _emit_htf_flat(ticker, interval, df, signals)

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
        # Max bars since the breakout bar (trigger_bar). For 1d: ≤2 bars (today
        # or yesterday's break); for 1h/4h: ≤3 bars; for 1w: ≤1 bar.
        _w3_max_age = {"1w": 1, "1d": 2, "4h": 3, "1h": 3}
        w3_fresh_bars = _w3_max_age.get(str(interval), 2)
        closes = df["close"].values
        opens = df["open"].values

        def _w3_trigger_bar(setup) -> int | None:
            """Return bar index where price FIRST crossed the breakout level.

            Walks back from last_idx to find the bar that crossed entry_px.
            Returns None if the crossing is older than w3_fresh_bars.
            """
            ep = setup.entry_px
            short = setup.side == "short"
            # Walk back to find the last bar that was on the 'pre-trigger' side.
            for i in range(last_idx - 1, max(-1, last_idx - w3_fresh_bars - 2), -1):
                c = float(closes[i])
                was_pre = c >= ep if short else c <= ep
                if was_pre:
                    trig = i + 1   # bar after the last pre-trigger bar
                    if last_idx - trig <= w3_fresh_bars:
                        return trig
                    return None   # stale
            return None  # crossed too far back or not found in window

        # Many past W1/W2 triples can still be "triggered"; keep only the
        # freshest setup per side (largest trigger_bar) to avoid flooding.
        freshest: dict[str, object] = {}
        for setup in detect_wave3_setups(pivots, last_px, last_idx):
            if not (setup.triggered and setup.struct_ok and setup.rr1 >= 1.0):
                continue
            tbar = _w3_trigger_bar(setup)
            if tbar is None:
                continue   # stale breakout — entry opportunity already passed
            cur = freshest.get(setup.side)
            if cur is None or tbar > cur[1]:
                freshest[setup.side] = (setup, tbar)

        for setup, tbar in freshest.values():
            # next_open execution: enter at the open of the bar AFTER the trigger.
            exec_bar = tbar + 1
            if exec_bar > last_idx:
                exec_bar = last_idx   # current bar is best available approx
            actual_entry = float(opens[exec_bar])
            actual_ts = str(df.index[exec_bar])

            sig = setup.to_signal(ticker, interval, actual_ts)
            # Override entry_px with actual fill price; keep structural stop/target.
            rb = sig["risk_box"]
            rb["entry_px"] = actual_entry
            rb["structural_entry"] = setup.entry_px   # preserve for reference
            # Guard negative targets: can happen when w1_len > entry_px for
            # low-priced assets on a short. Cap target at 1% of entry price.
            if rb["target_px"] <= 0:
                rb["target_px"] = max(rb["entry_px"] * 0.01, 1e-8)
            # Recalculate R:R from actual entry (stop/target stay structural)
            risk = abs(actual_entry - rb["stop_px"])
            reward = abs(rb["target_px"] - actual_entry)
            if risk <= 0 or reward / risk < 1.0:
                continue   # entry overshot structural level, R:R invalid
            wr, n = w3_wr.get((asset, interval, setup.side), (0.0, 0))
            sig["p_trade_win"] = wr
            sig["sample_size"] = n
            signals.append(sig)

    # EPIC F: Neely core setups (triangle thrust, post-W4, ...). Reward-first
    # gate + MIN_RR select the profitable, high-R:R ones (triangle thrust).
    _emit_core_setups(ticker, interval, df, figures, signals)
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
