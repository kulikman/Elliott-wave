"""EPIC 3 — Forward Validation Tracker for Wave-3 engine.

Runs with EWB_WAVE3=1 and tracks W3 setups through their lifecycle:
  OPEN → (triggered) → TP1/TP2/TP3 HIT | SL HIT | INVALID | EXPIRED

Usage:
    python python/scripts/w3_forward_tracker.py          # one pass + update
    python python/scripts/w3_forward_tracker.py --reset  # clear all history

Stores:
    brain-output/backtests/w3_setups_open.json    — active setups
    brain-output/backtests/w3_setups_closed.jsonl  — completed setups (append)
    brain-output/backtests/w3_forward_report.json  — summary metrics

Promote W3 to primary Action when:
    - n_closed >= 30 AND
    - W3 profit_factor >= 1.5 AND W3 win_rate >= 55% AND
    - W3 expectancy > fade baseline (from ewb_backtest_vs_forward.json)
"""
from __future__ import annotations
import os, sys, json, time, argparse
from datetime import datetime, timezone
from pathlib import Path

# ── path setup ──────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))
os.environ.setdefault("EWB_WAVE3", "1")

import yfinance as yf
import pandas as pd

from ewb.monowaves import detect_monowaves
from ewb.rules import classify_pivots
from ewb.wave3 import detect_wave3_setups

# ── paths ────────────────────────────────────────────────────────────────────
BACKTEST_DIR = ROOT / "brain-output" / "backtests"
BACKTEST_DIR.mkdir(parents=True, exist_ok=True)
OPEN_FILE    = BACKTEST_DIR / "w3_setups_open.json"
CLOSED_FILE  = BACKTEST_DIR / "w3_setups_closed.jsonl"
REPORT_FILE  = BACKTEST_DIR / "w3_forward_report.json"

# ── config ────────────────────────────────────────────────────────────────────
W3_MIN_RR = 1.0          # minimum RR1 to record a setup
EXPIRY_BARS = 200        # bars without resolution → expired
PROMOTE_N   = 30         # minimum closed trades to consider promotion
PROMOTE_PF  = 1.5        # minimum profit factor
PROMOTE_WR  = 0.55       # minimum win rate

# Watchlist (matches configs/watchlist.yaml)
def _load_watchlist() -> tuple[list[str], list[str]]:
    import yaml
    cfg_path = ROOT / "configs" / "watchlist.yaml"
    if not cfg_path.exists():
        return [], []
    with open(cfg_path) as f:
        d = yaml.safe_load(f)
    stocks = list(d.get("stocks", []))
    crypto = list(d.get("crypto", []))
    intervals = [str(i) for i in d.get("intervals", ["1d", "4h", "1h"])]
    return stocks + crypto, intervals


# ── data fetch ───────────────────────────────────────────────────────────────
_PERIOD_MAP = {"1d": "6mo", "4h": "3mo", "1h": "2mo", "30m": "1mo", "15m": "15d"}

def _fetch_ohlc(ticker: str, interval: str) -> pd.DataFrame | None:
    period = _PERIOD_MAP.get(interval, "3mo")
    try:
        df = yf.download(ticker, period=period, interval=interval,
                         auto_adjust=True, progress=False, timeout=10)
        if df is None or len(df) < 30:
            return None
        df.columns = [c.lower() for c in df.columns]
        df = df.dropna(subset=["close"])
        return df
    except Exception:
        return None


# ── setup detection ──────────────────────────────────────────────────────────
def scan_for_setups(tickers: list[str], intervals: list[str]) -> list[dict]:
    """Scan all tickers/intervals and return list of W3 setup dicts."""
    setups_out = []
    ts = datetime.now(timezone.utc).isoformat()
    for ticker in tickers:
        for interval in intervals:
            df = _fetch_ohlc(ticker, interval)
            if df is None:
                continue
            pivots = detect_monowaves(df, atr_mult=2.5)
            if len(pivots) < 3:
                continue
            classify_pivots(pivots)
            last_idx = len(df) - 1
            last_px  = float(df["close"].iloc[last_idx])
            for setup in detect_wave3_setups(pivots, last_px, last_idx):
                if setup.rr1 < W3_MIN_RR:
                    continue
                sig = setup.to_signal(ticker, interval, ts)
                sig["scan_ts"]  = ts
                sig["last_bar"] = last_idx
                sig["status"]   = "TRIGGERED" if setup.triggered else "WAITING"
                # Store raw prices needed for outcome tracking
                sig["_w1_start"]   = setup.w1_start
                sig["_w1_end"]     = setup.w1_end
                sig["_w2_end"]     = setup.w2_end
                sig["_struct_ok"]  = setup.struct_ok
                setups_out.append(sig)
    return setups_out


# ── open setups store ─────────────────────────────────────────────────────────
def _load_open() -> list[dict]:
    if not OPEN_FILE.exists():
        return []
    with open(OPEN_FILE) as f:
        return json.load(f)

def _save_open(setups: list[dict]) -> None:
    with open(OPEN_FILE, "w") as f:
        json.dump(setups, f, indent=2)

def _append_closed(setup: dict) -> None:
    with open(CLOSED_FILE, "a") as f:
        f.write(json.dumps(setup) + "\n")


# ── outcome check ─────────────────────────────────────────────────────────────
def check_outcome(setup: dict) -> dict | None:
    """Fetch latest price for this setup and determine if it resolved.

    Returns updated setup dict with 'outcome' field, or None if still open.
    """
    ticker   = setup["ticker"]
    interval = setup["interval"]
    df = _fetch_ohlc(ticker, interval)
    if df is None:
        return None

    entry    = setup["risk_box"]["entry_px"]
    stop     = setup["risk_box"]["stop_px"]
    tp1      = setup["risk_box"]["tp1"]
    tp2      = setup["risk_box"].get("target_px", setup["risk_box"].get("tp2", entry))
    tp3      = setup["risk_box"]["tp3"]
    invalid  = setup["risk_box"]["invalid_px"]
    side     = setup["side"]              # "long" / "short"
    last_bar = setup.get("last_bar", 0)
    current_bars = len(df) - 1
    bars_elapsed = current_bars - last_bar

    # Expiry check
    if bars_elapsed >= EXPIRY_BARS:
        setup["outcome"]       = "EXPIRED"
        setup["close_ts"]      = datetime.now(timezone.utc).isoformat()
        setup["bars_held"]     = bars_elapsed
        setup["final_px"]      = float(df["close"].iloc[-1])
        return setup

    # Scan bars since entry for outcome
    start_bar = max(0, last_bar)
    for i in range(start_bar, len(df)):
        h = float(df["high"].iloc[i])
        l = float(df["low"].iloc[i])
        if side == "long":
            if l <= stop:
                setup["outcome"] = "SL_HIT"
                break
            if l <= invalid:
                setup["outcome"] = "INVALID"
                break
            if h >= tp3:
                setup["outcome"] = "TP3_HIT"
                break
            if h >= tp2:
                setup["outcome"] = "TP2_HIT"
                break
            if h >= tp1:
                setup["outcome"] = "TP1_HIT"
                break
        else:  # short
            if h >= stop:
                setup["outcome"] = "SL_HIT"
                break
            if h >= invalid:
                setup["outcome"] = "INVALID"
                break
            if l <= tp3:
                setup["outcome"] = "TP3_HIT"
                break
            if l <= tp2:
                setup["outcome"] = "TP2_HIT"
                break
            if l <= tp1:
                setup["outcome"] = "TP1_HIT"
                break

    if "outcome" not in setup:
        return None  # still open

    setup["close_ts"]  = datetime.now(timezone.utc).isoformat()
    setup["bars_held"] = bars_elapsed
    setup["final_px"]  = float(df["close"].iloc[-1])
    return setup


# ── metrics ────────────────────────────────────────────────────────────────────
def compute_metrics(closed: list[dict]) -> dict:
    if not closed:
        return {"n": 0, "status": "insufficient_data"}

    wins   = [s for s in closed if s.get("outcome","").startswith("TP")]
    losses = [s for s in closed if s.get("outcome") in ("SL_HIT", "INVALID")]
    expired = [s for s in closed if s.get("outcome") == "EXPIRED"]

    n_closed = len(closed)
    n_wins   = len(wins)
    n_losses = len(losses)
    n_exp    = len(expired)
    win_rate = n_wins / (n_wins + n_losses) if (n_wins + n_losses) > 0 else 0.0

    # Profit factor: average win / average loss (in W1 multiples)
    avg_win_r = sum(
        1.0 if s["outcome"] == "TP1_HIT" else
        1.618 if s["outcome"] == "TP2_HIT" else
        2.618 for s in wins
    ) / n_wins if n_wins > 0 else 0.0
    avg_loss_r = 1.0  # loss = full 1×risk (stop at W2 end = 1R from entry)
    pf = (n_wins * avg_win_r) / (n_losses * avg_loss_r) if n_losses > 0 else float("inf")

    # Expectancy (in R)
    expectancy = win_rate * avg_win_r - (1 - win_rate) * avg_loss_r

    # Breakdown by TP level
    tp1_ct = sum(1 for s in wins if s["outcome"] == "TP1_HIT")
    tp2_ct = sum(1 for s in wins if s["outcome"] == "TP2_HIT")
    tp3_ct = sum(1 for s in wins if s["outcome"] == "TP3_HIT")

    # Promotion check
    promotable = (
        n_closed >= PROMOTE_N and
        pf >= PROMOTE_PF and
        win_rate >= PROMOTE_WR
    )

    return {
        "n_closed": n_closed,
        "n_wins": n_wins,
        "n_losses": n_losses,
        "n_expired": n_exp,
        "win_rate": round(win_rate, 3),
        "avg_win_r": round(avg_win_r, 3),
        "profit_factor": round(pf, 3) if pf != float("inf") else "∞",
        "expectancy_r": round(expectancy, 3),
        "tp1_hits": tp1_ct,
        "tp2_hits": tp2_ct,
        "tp3_hits": tp3_ct,
        "promotable": promotable,
        "promote_criteria": {
            "n_min": PROMOTE_N,
            "pf_min": PROMOTE_PF,
            "wr_min": PROMOTE_WR,
        },
        "status": "READY_TO_PROMOTE" if promotable else f"need {max(0, PROMOTE_N - n_closed)} more trades",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _load_closed() -> list[dict]:
    if not CLOSED_FILE.exists():
        return []
    out = []
    with open(CLOSED_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return out


# ── main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="EWB W3 Forward Tracker")
    parser.add_argument("--reset", action="store_true", help="Clear all open/closed history")
    parser.add_argument("--scan-only", action="store_true", help="Scan for new setups without checking outcomes")
    parser.add_argument("--report-only", action="store_true", help="Print report only (no scan)")
    args = parser.parse_args()

    if args.reset:
        OPEN_FILE.unlink(missing_ok=True)
        CLOSED_FILE.unlink(missing_ok=True)
        REPORT_FILE.unlink(missing_ok=True)
        print("[w3_tracker] Reset complete.")
        return

    if args.report_only:
        closed = _load_closed()
        metrics = compute_metrics(closed)
        print(json.dumps(metrics, indent=2))
        return

    tickers, intervals = _load_watchlist()
    if not tickers:
        print("[w3_tracker] No tickers in watchlist. Exiting.")
        return

    # ── Step 1: check outcomes on open setups ──────────────────────────────
    if not args.scan_only:
        open_setups = _load_open()
        still_open  = []
        resolved = 0
        print(f"[w3_tracker] Checking {len(open_setups)} open setup(s)...")
        for s in open_setups:
            updated = check_outcome(s)
            if updated is not None:
                _append_closed(updated)
                resolved += 1
                print(f"  → {s['ticker']} {s['interval']} {s['side'].upper()} → {updated['outcome']}")
            else:
                still_open.append(s)
        _save_open(still_open)
        print(f"[w3_tracker] {resolved} resolved, {len(still_open)} still open.")

    # ── Step 2: scan for new setups ────────────────────────────────────────
    print(f"[w3_tracker] Scanning {len(tickers)} tickers × {intervals}...")
    new_setups = scan_for_setups(tickers, intervals)
    print(f"[w3_tracker] Found {len(new_setups)} new setup(s).")

    # De-duplicate: don't re-add same ticker+interval+side that's already open
    open_keys = {(s["ticker"], s["interval"], s["side"]) for s in _load_open()}
    added = 0
    fresh_open = list(_load_open())
    for s in new_setups:
        key = (s["ticker"], s["interval"], s["side"])
        if key not in open_keys:
            fresh_open.append(s)
            open_keys.add(key)
            added += 1
            print(f"  + {s['ticker']} {s['interval']} {s['side'].upper()} "
                  f"status={s['status']} W2={round(s.get('w2_retrace',0)*100)}% "
                  f"RR1={s.get('rr1',0):.2f}")
    _save_open(fresh_open)
    print(f"[w3_tracker] Added {added} new setup(s). Total open: {len(fresh_open)}.")

    # ── Step 3: recompute metrics ──────────────────────────────────────────
    closed  = _load_closed()
    metrics = compute_metrics(closed)
    with open(REPORT_FILE, "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"\n[w3_tracker] === FORWARD REPORT ===")
    print(f"  Closed:    {metrics.get('n_closed', 0)}")
    print(f"  Wins:      {metrics.get('n_wins', 0)}")
    print(f"  Losses:    {metrics.get('n_losses', 0)}")
    print(f"  Win rate:  {metrics.get('win_rate', 0):.1%}")
    print(f"  Profit F:  {metrics.get('profit_factor', 0)}")
    print(f"  Expect/R:  {metrics.get('expectancy_r', 0):.3f}")
    print(f"  Status:    {metrics.get('status', '?')}")
    if metrics.get("promotable"):
        print("\n  *** W3 ENGINE READY TO PROMOTE TO PRIMARY ACTION ***")


if __name__ == "__main__":
    main()
