"""Autonomous paper trader for Elliott Wave Brain.

Loop (every N minutes):
  1. Scan watchlist → find REVIEW signals
  2. Open paper trades for new signals (dedup by signal_id)
  3. Check open trades → close on TP/SL/timeout
  4. After every RETRAIN_EVERY closed trades → retrain LightGBM
  5. Log everything to FORWARD_LOG (JSONL)

Run:
    python -m ewb.auto_trader            # foreground, Ctrl-C to stop
    python -m ewb.auto_trader --once     # single pass, useful for cron
    python -m ewb.auto_trader --status   # print current state and exit
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import pickle
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]   # …/python/ewb/auto_trader.py → …/Elliott-wave
sys.path.insert(0, str(ROOT / "python"))

from ewb.strategy_system import (
    DEFAULT_FORWARD_LOG,
    append_jsonl,
    forward_trades,
    note_event,
    outcome_event,
    read_jsonl,
    signal_event,
    stable_signal_id,
    utc_now_iso,
)

WATCHLIST      = ROOT / "configs" / "watchlist.yaml"
SIGNALS_DIR    = ROOT / "brain-output" / "signals"
FORWARD_LOG    = ROOT / DEFAULT_FORWARD_LOG
MODEL_OUT      = ROOT / "brain-output" / "models"
STATE_FILE     = ROOT / "brain-output" / "auto_trader_state.json"
LOG_FILE       = ROOT / "brain-output" / "auto_trader.log"

SCAN_INTERVAL  = 60 * 60        # re-scan every 60 min
MIN_P_WIN      = 0.55           # minimum p_trade_win to open a trade
MIN_RR         = 1.0            # minimum risk-reward ratio
MAX_OPEN       = 5              # max concurrent open paper trades
TIMEOUT_BARS   = 30             # close trade after N bars if still open
RETRAIN_EVERY  = 20             # retrain ML after every N closed trades

# NYSE/NASDAQ session: Mon-Fri 09:30–16:00 ET
ET = ZoneInfo("America/New_York")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
log = logging.getLogger("auto_trader")


# ─── helpers ────────────────────────────────────────────────────────────────

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def market_status(interval: str = "1d") -> str:
    """Return 'open', 'post_close', or 'closed'.

    For daily TF we care about 'post_close' (16:00-20:00 ET) — the candle is
    finalised and we can evaluate TP/SL against today's close.
    For intraday TF we need 'open' (09:30-16:00 ET).
    """
    now_et = datetime.now(ET)
    weekday = now_et.weekday()   # 0=Mon … 4=Fri
    if weekday >= 5:             # weekend
        return "closed"
    t = now_et.time()
    from datetime import time as _time
    market_open  = _time(9, 30)
    market_close = _time(16, 0)
    post_close   = _time(20, 0)
    if t < market_open:
        return "closed"          # pre-market
    if t < market_close:
        return "open"
    if t < post_close:
        return "post_close"      # after-hours, daily candle finalised
    return "closed"


def should_trade(interval: str) -> tuple[bool, str]:
    """Return (allowed, reason) for current time and interval."""
    status = market_status(interval)
    if interval in ("1d", "1w"):
        # Daily/weekly: evaluate TP/SL once after session closes
        if status in ("open", "post_close"):
            return True, status
        return False, f"market {status} — waiting for US session"
    else:
        # Intraday: only during open session
        if status == "open":
            return True, "open"
        return False, f"market {status} — intraday only trades during session"


def read_watchlist() -> dict[str, Any]:
    if not WATCHLIST.exists():
        return {"tickers": [], "interval": "1d"}
    return yaml.safe_load(WATCHLIST.read_text(encoding="utf-8")) or {}


def read_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {"closed_since_retrain": 0, "last_scan": None, "last_retrain": None}
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def write_state(state: dict[str, Any]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def current_price(ticker: str) -> float | None:
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).fast_info
        px = info.last_price
        return float(px) if px and math.isfinite(px) else None
    except Exception:
        return None


def current_prices(tickers: list[str]) -> dict[str, float | None]:
    if not tickers:
        return {}
    try:
        import yfinance as yf
        batch = yf.Tickers(" ".join(tickers))
        result: dict[str, float | None] = {}
        for sym in tickers:
            try:
                px = batch.tickers[sym.upper()].fast_info.last_price
                result[sym.upper()] = float(px) if px and math.isfinite(px) else None
            except Exception:
                result[sym.upper()] = None
        return result
    except Exception:
        return {t.upper(): None for t in tickers}


def rr(entry: float, stop: float, target: float) -> float:
    risk   = abs(entry - stop)
    reward = abs(target - entry)
    return reward / risk if risk > 0 else 0.0


# ─── scanner ────────────────────────────────────────────────────────────────

def run_scan(tickers: list[str], interval: str) -> list[dict]:
    """Run probability scan and return list of signal dicts."""
    if not tickers:
        return []
    log.info("Scanning %d tickers on %s …", len(tickers), interval)
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "python" / "scripts" / "scan_probability_signals.py"),
            "--tickers", ",".join(tickers),
            "--interval", interval,
            "--limit", "50",
            "--actions", "buy,sell",
            "--save",
            "--output-dir", str(SIGNALS_DIR),
        ],
        capture_output=True, text=True, cwd=ROOT,
    )
    if result.returncode != 0:
        log.warning("scan stderr: %s", result.stderr[-500:])

    # Read saved JSON
    fname = f"probability_signals_{interval}_buy-sell.json"
    path = SIGNALS_DIR / fname
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("signals", [])


# ─── open trades ────────────────────────────────────────────────────────────

def open_signal_ids(events: list[dict]) -> set[str]:
    trades = forward_trades(events)
    if trades.empty:
        return set()
    open_df = trades[trades["status"] == "open"]
    return set(open_df["signal_id"].tolist())


def dedup_key(sig: dict) -> str:
    """Stable dedup key — one trade per ticker+interval+side per day."""
    entry_day = str(sig.get("entry_ts", ""))[:10]
    return f"{sig['ticker']}|{sig.get('interval','?')}|{sig.get('side','?')}|{entry_day}"


def try_open_trades(signals: list[dict], events: list[dict]) -> int:
    """Open paper trades for qualifying signals. Returns count opened."""
    trades = forward_trades(events)
    n_open = 0 if trades.empty else int((trades["status"] == "open").sum())
    if n_open >= MAX_OPEN:
        log.info("Max open trades (%d) reached, skipping open step", MAX_OPEN)
        return 0

    # Build dedup keys of already-opened signals
    existing_keys: set[str] = set()
    if not trades.empty:
        for _, row in trades.iterrows():
            day = str(row.get("entry_ts", ""))[:10]
            existing_keys.add(f"{row['ticker']}|{row['interval']}|{row['side']}|{day}")

    opened = 0
    for sig in signals:
        if n_open + opened >= MAX_OPEN:
            break

        rb = sig.get("risk_box", {})
        entry_px  = rb.get("entry_px")
        stop_px   = rb.get("stop_px")
        target_px = rb.get("target_px")
        p_win     = sig.get("p_trade_win", 0.0)
        action    = sig.get("recommended_action", "")

        # Quality gates
        if entry_px is None or stop_px is None or target_px is None:
            continue
        if p_win < MIN_P_WIN:
            continue
        if rr(entry_px, stop_px, target_px) < MIN_RR:
            continue
        if action not in ("buy", "sell"):
            continue

        # Dedup
        entry_day = str(sig.get("entry_ts", ""))[:10]
        key = f"{sig['ticker']}|{sig.get('interval','?')}|{'long' if action=='buy' else 'short'}|{entry_day}"
        if key in existing_keys:
            continue

        # Build signal event
        row = signal_event(
            ticker      = sig["ticker"],
            interval    = sig.get("interval", "1d"),
            action      = action,
            entry_ts    = sig.get("entry_ts", utc_now_iso()),
            entry_px    = entry_px,
            stop_px     = stop_px,
            target_px   = target_px,
            fig_type    = sig.get("pattern", "unknown"),
            probability = p_win * 100,
            htf_context = f"auto_trader | p={p_win:.2f} | lag={sig.get('confirmation_lag',0)}d",
            source      = "auto_trader",
        )
        append_jsonl(FORWARD_LOG, row)
        existing_keys.add(key)
        opened += 1
        log.info(
            "OPEN  %-6s %-5s  %s  entry=%.2f stop=%.2f target=%.2f p=%.1f%%",
            row["ticker"], row["side"], row["interval"],
            entry_px, stop_px, target_px, p_win * 100,
        )

    if opened:
        log.info("Opened %d new paper trade(s)", opened)
    return opened


# ─── close trades ───────────────────────────────────────────────────────────

def try_close_trades(events: list[dict]) -> int:
    """Check open trades against live prices; close on TP/SL/timeout. Returns count closed."""
    trades = forward_trades(events)
    if trades.empty:
        return 0
    open_df = trades[trades["status"] == "open"]
    if open_df.empty:
        return 0

    tickers = open_df["ticker"].unique().tolist()
    prices  = current_prices(tickers)
    closed  = 0
    now     = utc_now()

    for _, trade in open_df.iterrows():
        ticker    = trade["ticker"]
        px        = prices.get(ticker)
        if px is None:
            continue

        entry_px  = float(trade["entry_px"])
        stop_px   = float(trade.get("stop_px") or 0)
        target_px = float(trade.get("target_px") or 0)
        side      = trade.get("side", "long")
        signal_id = trade["signal_id"]

        # Timeout check (in trading days)
        entry_ts  = pd.Timestamp(trade["entry_ts"]).tz_convert("UTC")
        bars_held = (now - entry_ts).days
        if bars_held > TIMEOUT_BARS:
            reason = "timeout"
        elif side == "long":
            if stop_px > 0 and px <= stop_px:
                reason = "sl"
            elif target_px > 0 and px >= target_px:
                reason = "tp"
            else:
                continue
        else:  # short
            if stop_px > 0 and px >= stop_px:
                reason = "sl"
            elif target_px > 0 and px <= target_px:
                reason = "tp"
            else:
                continue

        evt = outcome_event(
            signal_id  = signal_id,
            exit_ts    = now.isoformat(),
            exit_px    = px,
            exit_reason= reason,
        )
        append_jsonl(FORWARD_LOG, evt)
        closed += 1
        direction = 1 if side == "long" else -1
        ret_pct   = direction * (px - entry_px) / entry_px * 100
        log.info(
            "CLOSE %-6s %-5s  reason=%-7s exit=%.2f ret=%+.1f%%",
            ticker, side, reason, px, ret_pct,
        )

    if closed:
        log.info("Closed %d trade(s)", closed)
    return closed


# ─── ML retraining ──────────────────────────────────────────────────────────

def retrain_model() -> bool:
    """Rebuild dataset and retrain LightGBM. Returns True on success."""
    log.info("Retraining LightGBM model …")
    try:
        r1 = subprocess.run(
            [sys.executable, str(ROOT / "python" / "scripts" / "build_dataset.py")],
            capture_output=True, text=True, cwd=ROOT, timeout=600,
        )
        if r1.returncode != 0:
            log.warning("build_dataset stderr: %s", r1.stderr[-300:])

        r2 = subprocess.run(
            [
                sys.executable,
                str(ROOT / "python" / "ewb" / "research" / "lgbm_model.py"),
                "--train", "--save-model",
            ],
            capture_output=True, text=True, cwd=ROOT, timeout=600,
        )
        if r2.returncode != 0:
            log.warning("lgbm_model stderr: %s", r2.stderr[-300:])
            return False

        log.info("Retrain complete. stdout: %s", r2.stdout[-300:])
        return True
    except Exception as e:
        log.error("Retrain failed: %s", e)
        return False


# ─── status report ──────────────────────────────────────────────────────────

def print_status() -> None:
    state  = read_state()
    events = read_jsonl(FORWARD_LOG)
    trades = forward_trades(events)

    n_open   = 0
    n_closed = 0
    wins     = 0
    if not trades.empty:
        n_open   = int((trades["status"] == "open").sum())
        closed_df = trades[trades["status"] == "closed"]
        n_closed = len(closed_df)
        wins     = int(closed_df["win"].sum()) if "win" in closed_df else 0

    wr = wins / n_closed * 100 if n_closed else 0
    print(f"\n{'─'*50}")
    print(f"  Auto-trader status  {utc_now_iso()}")
    print(f"{'─'*50}")
    print(f"  Open trades      : {n_open}")
    print(f"  Closed trades    : {n_closed}  WR={wr:.1f}%")
    print(f"  Since retrain    : {state.get('closed_since_retrain', 0)}/{RETRAIN_EVERY}")
    print(f"  Last scan        : {state.get('last_scan', 'never')}")
    print(f"  Last retrain     : {state.get('last_retrain', 'never')}")
    print(f"{'─'*50}\n")

    if not trades.empty:
        open_df = trades[trades["status"] == "open"]
        if not open_df.empty:
            print("  Open positions:")
            for _, r in open_df.iterrows():
                print(f"    {r['ticker']:<8} {r['side']:<5}  entry={r['entry_px']:.2f}  "
                      f"stop={r.get('stop_px',0):.2f}  target={r.get('target_px',0):.2f}")
        print()


# ─── main loop ──────────────────────────────────────────────────────────────

def one_pass() -> None:
    wl       = read_watchlist()
    tickers  = wl.get("tickers", [])
    interval = wl.get("interval", "1d")
    state    = read_state()

    allowed, reason = should_trade(interval)
    if not allowed:
        log.info("Session check: %s — skipping open/close (scan only)", reason)
        # Still run scan to pre-load signals for when session opens
        run_scan(tickers, interval)
        state["last_scan"] = utc_now_iso()
        write_state(state)
        return

    log.info("Session check: %s ✓", reason)

    # 1. Scan
    signals = run_scan(tickers, interval)
    state["last_scan"] = utc_now_iso()
    log.info("Scan returned %d signal(s)", len(signals))

    # 2. Open new trades
    events  = read_jsonl(FORWARD_LOG)
    opened  = try_open_trades(signals, events)

    # 3. Close trades on TP/SL/timeout (only with real finalised prices)
    events  = read_jsonl(FORWARD_LOG)        # reload after writes
    closed  = try_close_trades(events)

    # 4. Retrain if enough new closed trades
    state["closed_since_retrain"] = state.get("closed_since_retrain", 0) + closed
    if state["closed_since_retrain"] >= RETRAIN_EVERY:
        ok = retrain_model()
        if ok:
            state["closed_since_retrain"] = 0
            state["last_retrain"] = utc_now_iso()

    write_state(state)
    log.info(
        "Pass done — opened=%d closed=%d pending_retrain=%d/%d",
        opened, closed, state["closed_since_retrain"], RETRAIN_EVERY,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="EWB autonomous paper trader")
    parser.add_argument("--once",   action="store_true", help="Single pass and exit")
    parser.add_argument("--status", action="store_true", help="Print status and exit")
    parser.add_argument("--interval", type=int, default=SCAN_INTERVAL,
                        help=f"Scan interval in seconds (default {SCAN_INTERVAL})")
    args = parser.parse_args()

    if args.status:
        print_status()
        return

    if args.once:
        one_pass()
        return

    log.info("Auto-trader started  scan_interval=%ds  max_open=%d  min_p=%.0f%%  retrain_every=%d",
             args.interval, MAX_OPEN, MIN_P_WIN * 100, RETRAIN_EVERY)
    while True:
        try:
            one_pass()
        except KeyboardInterrupt:
            log.info("Stopped by user")
            break
        except Exception as e:
            log.exception("Unexpected error in pass: %s", e)
        log.info("Sleeping %ds until next scan …", args.interval)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
