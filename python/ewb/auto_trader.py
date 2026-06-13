"""Autonomous paper trader for Elliott Wave Brain — US markets (NYSE/NASDAQ).

Exchange : NYSE / NASDAQ
Timezone : America/New_York (ET)
Session  : Mon–Fri 09:30–16:00 ET, excluding NYSE holidays
Daily TF : open + post_close (16:00–20:00) — candle finalised at 16:00
Intraday : open session only

Loop (every N minutes):
  1. Check NYSE calendar — skip if market closed/holiday
  2. Scan watchlist → find qualifying signals
  3. Open paper trades (p_win ≥ 55%, R:R ≥ 1.0, max 5 open)
  4. Check open trades → close on TP/SL/timeout
  5. After every RETRAIN_EVERY closed trades → retrain LightGBM

Run:
    python -m ewb.auto_trader            # foreground loop (Ctrl-C to stop)
    python -m ewb.auto_trader --once     # single pass
    python -m ewb.auto_trader --status   # print state and exit
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
import pickle
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    asset_class_of,
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
LOCK_FILE      = ROOT / "brain-output" / ".auto_trader.lock"
SETUP_WR_FILE  = ROOT / "brain-output" / "backtests" / "ewb_strategy_backtest_grouped.parquet"
WAVE3_WR_FILE  = ROOT / "brain-output" / "backtests" / "ewb_wave3_backtest_grouped.parquet"
CORE_WR_FILE   = ROOT / "brain-output" / "backtests" / "ewb_core_backtest_grouped.parquet"
HTFFLAT_WR_FILE = ROOT / "brain-output" / "backtests" / "ewb_htf_flat_backtest_grouped.parquet"

SCAN_INTERVAL  = 60 * 60        # re-scan every 60 min
MIN_P_WIN      = 0.50           # sanity floor only; real quality = EV gate (reward-first)
MIN_RR         = 1.0            # minimum risk-reward ratio
MAX_OPEN       = 0              # 0 = no limit on concurrent paper trades
TRADE_USD      = 100.0          # fixed paper trade size in USD
TIMEOUT_BARS   = 30             # default close-after-N-bars (fallback)
# Per-timeframe timeout: a W3 of a given degree must resolve within ~this many
# bars or the count was wrong. Scaled so a daily trade no longer hangs 6 weeks
# (30 daily bars) — the higher degree is the COMPASS, not the holding horizon.
TIMEOUT_BY_TF  = {"1h": 24, "4h": 18, "1d": 12, "1w": 6}
RETRAIN_EVERY  = 20             # retrain ML after every N closed trades

# ─── High-winrate setup gate (validated against the 1518-trade backtest) ──────
# The probability calibration was built on a small sample and over-rates some
# setups (e.g. stock flat-short: calib 70% vs real 47%). To enforce "only high
# win-rate signals", every candidate is cross-checked against the large strategy
# backtest grouped winrates. A setup that is not validated, has too few backtest
# trades, or sits below the winrate floor is blocked regardless of its p_win.
# Reward-first selection: the PRIMARY gate is expectancy (avg % return per
# trade), not win-rate. A 59%-WR setup that makes +4.6%/trade beats a 72%-WR
# scalp that makes +0.35% with reward<risk. SETUP_EV_FLOOR is the backtest
# expectancy floor; SETUP_WR_FLOOR is only a sanity floor. Both env-overridable.
SETUP_EV_FLOOR = float(os.environ.get("EWB_SETUP_EV_FLOOR", "0.005"))  # +0.5%/trade
SETUP_WR_FLOOR = float(os.environ.get("EWB_SETUP_WR_FLOOR", "0.45"))   # sanity only (reward-first: EV leads)
SETUP_MIN_N    = 20             # default min validated backtest trades for a setup to count
# Wave3 requires a higher sample floor — the few backtest groups that survive the
# EPIC-1 honest-fill filter are narrow; n<40 OOS makes WR estimates unreliable.
# Using 40 (not 50): crypto/1d/long gives n=45 OOS from ~1500d history — further
# raising the bar would block the only validated crypto setup without new data.
SETUP_MIN_N_BY_FIG: dict[str, int] = {"wave3": 40, "flat_htf": 30}
MIN_SAMPLE     = 10             # min calibration sample_size (kills n=1 garbage)
# Optional style: trade ONLY lower-TF entries (1h/4h) and skip 1d/1w. Off by
# default — 1d/1w keep their own validated edge. Flip with EWB_LTF_ONLY=1.
LTF_ONLY       = os.environ.get("EWB_LTF_ONLY", "0") == "1"
HTF_INTERVALS  = {"1d", "1w", "1D", "1W"}

# ─── Freshness gate — open only signals confirmed "now", not old backfill ─────
# The scanner returns the last confirmed pattern, whose entry bar can be weeks
# old. Opening such a trade just replays history (its TP/SL already happened) —
# not a real forward test. We only open a trade if the signal's entry bar is
# within ~1 bar of the current time, i.e. it just confirmed. Set env
# EWB_MAX_SIGNAL_AGE_DAYS to override the window globally (in days).
SIGNAL_MAX_AGE = {
    "15m": timedelta(minutes=45),
    "30m": timedelta(hours=1, minutes=30),
    "1h":  timedelta(hours=2),
    "4h":  timedelta(hours=9),
    "1d":  timedelta(days=2),     # covers the just-closed daily bar (today)
    "1w":  timedelta(days=9),
}
SIGNAL_MAX_AGE_DEFAULT = timedelta(days=2)

# Exchange configuration — US markets
EXCHANGE       = "NYSE"          # used for holiday calendar
ET             = ZoneInfo("America/New_York")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("auto_trader")


# ─── helpers ────────────────────────────────────────────────────────────────

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def market_status(interval: str = "1d") -> str:
    """Return 'open', 'post_close', or 'closed' for NYSE/NASDAQ.

    Checks official NYSE holiday calendar via pandas_market_calendars.
    For daily TF 'post_close' (16:00–20:00 ET) means the candle is finalised.
    """
    from datetime import time as _time
    try:
        import pandas_market_calendars as mcal
        import pandas as pd
        nyse  = mcal.get_calendar(EXCHANGE)
        today = pd.Timestamp.now(tz="America/New_York")
        sched = nyse.schedule(start_date=today.date(), end_date=today.date())
        if sched.empty:
            return "closed"     # holiday or weekend
    except Exception:
        # Fallback: simple weekday check
        if datetime.now(ET).weekday() >= 5:
            return "closed"

    now_et = datetime.now(ET)
    t = now_et.time()
    market_open  = _time(9, 30)
    market_close = _time(16, 0)
    post_close   = _time(20, 0)
    if t < market_open:
        return "closed"
    if t < market_close:
        return "open"
    if t < post_close:
        return "post_close"     # after-hours, daily candle finalised
    return "closed"


CRYPTO_SUFFIXES = ("-USD", "-USDT", "-BTC", "-ETH", "-PERP")

def is_crypto(ticker: str) -> bool:
    t = ticker.upper()
    return any(t.endswith(s) for s in CRYPTO_SUFFIXES)


def should_trade_ticker(ticker: str, interval: str) -> tuple[bool, str]:
    """Return (allowed, reason) for a single ticker."""
    if is_crypto(ticker):
        return True, "crypto 24/7"
    status = market_status(interval)
    if interval in ("1d", "1w"):
        if status in ("open", "post_close"):
            return True, status
        return False, f"NYSE {status}"
    else:
        if status == "open":
            return True, "open"
        return False, f"NYSE {status} — intraday only during session"


def split_by_session(tickers: list[str], interval: str) -> tuple[list[str], list[str]]:
    """Return (tradeable_now, scan_only) based on current session."""
    tradeable, scan_only = [], []
    for t in tickers:
        ok, _ = should_trade_ticker(t, interval)
        (tradeable if ok else scan_only).append(t)
    return tradeable, scan_only


def read_watchlist() -> dict[str, Any]:
    if not WATCHLIST.exists():
        return {"stocks": [], "crypto": [], "intervals": ["1d"]}
    return yaml.safe_load(WATCHLIST.read_text(encoding="utf-8")) or {}


def wl_all_tickers(wl: dict) -> list[str]:
    if "stocks" in wl or "crypto" in wl:
        return [str(t).upper() for t in wl.get("stocks", [])] + \
               [str(t).upper() for t in wl.get("crypto", [])]
    return [str(t).upper() for t in wl.get("tickers", [])]


def wl_intervals(wl: dict) -> list[str]:
    if "intervals" in wl:
        return [str(i) for i in wl["intervals"]]
    return [str(wl.get("interval", "1d"))]


def read_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {"closed_since_retrain": 0, "last_scan": None, "last_retrain": None}
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def write_state(state: dict[str, Any]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def current_price(ticker: str) -> float | None:
    # Provider first (Binance/Tiingo), yfinance fallback.
    try:
        from ewb.research.providers import last_price
        px = last_price(ticker)
        if px and math.isfinite(px):
            return float(px)
    except Exception:
        pass
    try:
        import yfinance as yf
        px = yf.Ticker(ticker).fast_info.last_price
        return float(px) if px and math.isfinite(px) else None
    except Exception:
        return None


def rr(entry: float, stop: float, target: float) -> float:
    risk   = abs(entry - stop)
    reward = abs(target - entry)
    return reward / risk if risk > 0 else 0.0


# ─── verifiable historical exit ───────────────────────────────────────────────
# An open trade must be closed at the price that the market actually printed on
# the bar where SL / TP / timeout occurred — NOT at today's live price. Closing a
# months-old trade at the current quote produced hallucinated exits (e.g. MU
# entered 230 then "closed" at 892). We walk the real OHLC from the entry bar
# forward and exit at the first bar that hits SL or TP, otherwise at the close of
# the timeout bar. Every exit price is thus checkable against the chart.

def historical_exit(
    ticker: str,
    interval: str,
    entry_ts: pd.Timestamp,
    entry_px: float,
    stop_px: float,
    target_px: float,
    side: str,
    timeout_bars: int = TIMEOUT_BARS,
) -> tuple[pd.Timestamp, float, str] | None:
    """Replay real OHLC after entry and return (exit_ts, exit_px, reason).

    SL/TP exits use the stop/target level (the price the order would fill at);
    timeout exits use the close of the timeout bar. Returns None if no usable
    history is available (caller should then leave the trade open). Data comes
    from the same provider layer as the scanner (Binance/Tiingo, yfinance
    fallback) so exit prices match what the chart shows.
    """
    from ewb.research.data import download_ohlc

    interval = str(interval)
    entry_ts = pd.Timestamp(entry_ts)
    if entry_ts.tzinfo is None:
        entry_ts = entry_ts.tz_localize("UTC")

    # Enough history to cover entry -> now with a buffer.
    days = max(7, (utc_now() - entry_ts).days + 5)
    df = download_ohlc(ticker, interval, f"{days}d", min_rows=0)
    if df is None or df.empty:
        return None
    if not {"open", "high", "low", "close"}.issubset(df.columns):
        return None

    idx = pd.to_datetime(df.index, utc=True)
    df = df.set_axis(idx)
    after = df[df.index > entry_ts]
    if after.empty:
        return None

    walk = after.iloc[:max(1, timeout_bars)]
    is_long = str(side).lower() in ("long", "buy")

    for ts, bar in walk.iterrows():
        hi, lo, op = float(bar["high"]), float(bar["low"]), float(bar["open"])
        if is_long:
            hit_sl = stop_px > 0 and lo <= stop_px
            hit_tp = target_px > 0 and hi >= target_px
        else:
            hit_sl = stop_px > 0 and hi >= stop_px
            hit_tp = target_px > 0 and lo <= target_px
        # If both levels fall inside one bar, assume the stop filled first.
        # Gap-realistic: if price opened beyond the stop, fill at the open
        # (live order would have filled at the gap open, not the stop level).
        if hit_sl:
            fill = min(stop_px, op) if is_long else max(stop_px, op)
            return ts, fill, "sl"
        if hit_tp:
            return ts, float(target_px), "tp"

    last_ts = walk.index[-1]
    last_close = float(walk.iloc[-1]["close"])
    reason = "timeout" if len(after) >= timeout_bars else "open_end"
    return last_ts, last_close, reason


# ─── HTF bias-flip exit ───────────────────────────────────────────────────────
# Event-driven exit: close when the higher-degree compass (1D/1W) turns against
# the position — Neely's "the structure changed" exit. Replaces waiting out a
# fixed timer with reacting to the actual trend reversal. Checkable: we exit at
# the close of the bar where the flip was CONFIRMED, never today's live quote.

# Which higher degree governs each trade's timeframe (mirrors the scanner).
BIASFLIP_RULE  = {"1h": "1D", "4h": "1D", "1d": "1W"}
# Mode: "strong" → flip only on |bias|=2 against (two HTF monowaves agree);
#       "sign"   → flip as soon as bias sign opposes the position;
#       "off"    → disabled. Tunable for forward/backtest comparison.
BIASFLIP_MODE  = os.environ.get("EWB_BIASFLIP_MODE", "strong").lower()


def bias_flip_exit(
    ticker: str, interval: str, entry_ts: pd.Timestamp, side: str,
    timeout_bars: int = TIMEOUT_BARS,
) -> tuple[pd.Timestamp, float, str] | None:
    """First bar after entry where the HTF compass flips against the position.

    Returns (exit_ts, exit_px=close, "bias_flip") or None if no flip within the
    timeout window. Honors EWB_BIASFLIP_MODE (strong/sign/off).
    """
    if BIASFLIP_MODE == "off":
        return None
    rule = BIASFLIP_RULE.get(str(interval))
    if rule is None:
        return None

    from ewb.research.data import download_ohlc
    from ewb.htf import structural_trend_series

    entry_ts = pd.Timestamp(entry_ts)
    if entry_ts.tzinfo is None:
        entry_ts = entry_ts.tz_localize("UTC")
    # Need a long lookback so the HTF pivot ladder is established BEFORE entry —
    # a short window (entry→now) yields too few HTF pivots and a stuck compass.
    _compass_floor = {"1h": 180, "4h": 300, "1d": 400}.get(str(interval), 400)
    days = max(_compass_floor, (utc_now() - entry_ts).days + 5)
    df = download_ohlc(ticker, interval, f"{days}d", min_rows=0)
    if df is None or df.empty or "close" not in df.columns:
        return None
    df = df.set_axis(pd.to_datetime(df.index, utc=True))

    try:
        bias = structural_trend_series(df, rule)
    except Exception:
        return None

    after = df[df.index > entry_ts]
    if after.empty:
        return None
    after = after.iloc[:max(1, timeout_bars)]   # only within the holding window
    is_long = str(side).lower() in ("long", "buy")

    for ts, bar in after.iterrows():
        b = int(bias.get(ts, 0))
        if BIASFLIP_MODE == "sign":
            flipped = (b < 0) if is_long else (b > 0)
        else:  # "strong"
            flipped = (b <= -2) if is_long else (b >= 2)
        if flipped:
            return ts, float(bar["close"]), "bias_flip"
    return None


# ─── scanner ────────────────────────────────────────────────────────────────

def run_scan(tickers: list[str], interval: str) -> list[dict]:
    """Run probability scan and return list of signal dicts."""
    if not tickers:
        return []
    log.info("Сканирую %d тикеров на %s …", len(tickers), interval)
    # EPIC C: emit Wave-3 setups too (validated stock-long / crypto-short).
    scan_env = {**os.environ, "EWB_WAVE3": "1"}
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
        capture_output=True, text=True, cwd=ROOT, env=scan_env,
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


# ─── high-winrate setup gate ─────────────────────────────────────────────────
_SETUP_WR_CACHE: dict[tuple[str, str, str, str], tuple[float, int]] | None = None



def load_setup_winrates() -> dict[tuple[str, str, str, str], tuple[float, int]]:
    """Load validated (asset_class, interval, fig_type, side) → (winrate, n)
    from the large strategy backtest. Cached after first read."""
    global _SETUP_WR_CACHE
    if _SETUP_WR_CACHE is not None:
        return _SETUP_WR_CACHE
    lut: dict[tuple[str, str, str, str], tuple[float, int, float]] = {}
    # Main flat LUT + the W3 LUT (EPIC C) are merged so validated setups pass
    # the gate alongside flats. Value = (winrate, trades, expectancy).
    for wr_file in (SETUP_WR_FILE, WAVE3_WR_FILE, CORE_WR_FILE, HTFFLAT_WR_FILE):
        if not wr_file.exists():
            continue
        try:
            g = pd.read_parquet(wr_file)
            for _, r in g.iterrows():
                key = (str(r["asset_class"]), str(r["interval"]),
                       str(r["fig_type"]), str(r["side"]))
                ev = float(r["expectancy"]) if "expectancy" in g.columns and pd.notna(r["expectancy"]) else 0.0
                lut[key] = (float(r["winrate"]), int(r["trades"]), ev)
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("could not load setup winrates from %s: %s", wr_file.name, exc)
    _SETUP_WR_CACHE = lut
    return lut


def signal_is_fresh(sig: dict) -> tuple[bool, str]:
    """Allow only signals whose entry bar just confirmed (from today/now).

    Blocks old backfill so every opened trade is a genuine forward trade whose
    outcome lies in the future. Returns (ok, reason).
    """
    ets = sig.get("entry_ts")
    if not ets:
        return False, "no entry_ts"
    try:
        ts = pd.Timestamp(ets)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        ts = ts.tz_convert("UTC")
    except Exception:
        return False, f"bad entry_ts {ets!r}"

    interval = str(sig.get("interval", "1d"))
    env_days = os.environ.get("EWB_MAX_SIGNAL_AGE_DAYS")
    if env_days:
        try:
            max_age = timedelta(days=float(env_days))
        except ValueError:
            max_age = SIGNAL_MAX_AGE.get(interval, SIGNAL_MAX_AGE_DEFAULT)
    else:
        max_age = SIGNAL_MAX_AGE.get(interval, SIGNAL_MAX_AGE_DEFAULT)

    age = utc_now() - ts
    if age > max_age:
        def _fmt(td: timedelta) -> str:
            h = td.total_seconds() / 3600.0
            return f"{h/24:.1f}d" if h >= 24 else f"{h:.0f}h"
        return False, f"stale signal (entry {_fmt(age)} ago > {_fmt(max_age)})"
    return True, "fresh"


def setup_quality_ok(sig: dict) -> tuple[bool, str]:
    """Reward-first gate: only open setups with validated positive expectancy.

    Primary filter is backtest expectancy (avg % return per trade); win-rate is
    only a sanity floor. Returns (ok, reason).
    """
    sample = sig.get("sample_size")
    if sample is not None and int(sample) < MIN_SAMPLE:
        return False, f"calib sample n={sample}<{MIN_SAMPLE}"

    ticker   = sig.get("ticker", "")
    interval = str(sig.get("interval", "?"))
    fig      = str(sig.get("pattern", "unknown"))
    side     = str(sig.get("side", "?"))

    if LTF_ONLY and interval in HTF_INTERVALS:        # optional LTF-only style
        return False, f"LTF-only: {interval} entries off (EWB_LTF_ONLY=1)"

    key = (asset_class_of(ticker), interval, fig, side)

    lut = load_setup_winrates()
    if key not in lut:
        return False, f"unvalidated setup {key[0]}/{fig}/{side} (no backtest edge)"
    wr, n, ev = lut[key]
    min_n = SETUP_MIN_N_BY_FIG.get(fig, SETUP_MIN_N)
    if n < min_n:
        return False, f"thin backtest n={n}<{min_n}"
    if ev < SETUP_EV_FLOOR:                       # PRIMARY — reward first
        return False, f"low EV {ev:+.2%}<{SETUP_EV_FLOOR:+.2%}"
    if wr < SETUP_WR_FLOOR:                        # sanity floor
        return False, f"low WR {wr:.0%}<{SETUP_WR_FLOOR:.0%}"
    return True, f"EV {ev:+.2%} WR {wr:.0%} (n={n})"


def try_open_trades(signals: list[dict], events: list[dict]) -> int:
    """Open paper trades for qualifying signals. Returns count opened."""
    trades = forward_trades(events)

    # Build dedup keys of already-opened signals
    existing_keys: set[str] = set()
    if not trades.empty:
        for _, row in trades.iterrows():
            day = str(row.get("entry_ts", ""))[:10]
            existing_keys.add(f"{row['ticker']}|{row['interval']}|{row['side']}|{day}")

    opened = 0
    for sig in signals:

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
        # Freshness gate: open only signals confirmed now, not old backfill.
        fresh, freason = signal_is_fresh(sig)
        if not fresh:
            log.info("ПРОПУСК %-6s %-5s %s  — %s",
                     sig.get("ticker", "?"), sig.get("side", "?"),
                     sig.get("interval", "?"), freason)
            continue
        # Time-budget gate (AKU-0036/0038/0060): confirmation must arrive within
        # the final wave's duration, else the pattern is structurally suspect.
        if sig.get("time_budget_ok") is False:
            log.info("ПРОПУСК %-6s %-5s %s  — confirmation %s бар > волны C %s бар (AKU-0036)",
                     sig.get("ticker", "?"), sig.get("side", "?"), sig.get("interval", "?"),
                     sig.get("confirmation_lag"), sig.get("last_wave_bars"))
            continue
        # High-winrate gate: only open setups proven by the large backtest.
        ok, reason = setup_quality_ok(sig)
        if not ok:
            log.info("ПРОПУСК %-6s %-5s %s  — %s",
                     sig.get("ticker", "?"), sig.get("side", "?"),
                     sig.get("interval", "?"), reason)
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
        row["trade_usd"] = TRADE_USD          # fixed $100 per trade
        append_jsonl(FORWARD_LOG, row)
        existing_keys.add(key)
        opened += 1
        log.info(
            "ОТКРЫТ %-6s %-5s  %s  вход=%.2f stop=%.2f target=%.2f p=%.1f%%",
            row["ticker"], row["side"], row["interval"],
            entry_px, stop_px, target_px, p_win * 100,
        )

    if opened:
        log.info("Открыто новых бумажных сделок: %d", opened)
    return opened


# ─── close trades ───────────────────────────────────────────────────────────

def try_close_trades(events: list[dict], tradeable_set: set[str] | None = None) -> int:
    """Check open trades against live prices; close on TP/SL/timeout.

    tradeable_set: tickers allowed to trade right now (crypto always included).
    Stocks outside NYSE session are skipped — their prices are stale.
    """
    trades = forward_trades(events)
    if trades.empty:
        return 0
    open_df = trades[trades["status"] == "open"]
    if open_df.empty:
        return 0

    # Filter to tradeable tickers only
    if tradeable_set:
        open_df = open_df[open_df["ticker"].str.upper().isin(tradeable_set)]
    if open_df.empty:
        return 0

    closed  = 0

    for _, trade in open_df.iterrows():
        ticker    = trade["ticker"]
        entry_px  = float(trade["entry_px"])
        stop_px   = float(trade.get("stop_px") or 0)
        target_px = float(trade.get("target_px") or 0)
        side      = trade.get("side", "long")
        interval  = str(trade.get("interval", "1d"))
        signal_id = trade["signal_id"]
        entry_ts  = pd.Timestamp(trade["entry_ts"]).tz_convert("UTC")

        # Exit at the real historical bar (SL/TP/timeout) — never today's quote.
        tf_timeout = TIMEOUT_BY_TF.get(interval, TIMEOUT_BARS)
        result = historical_exit(
            ticker, interval, entry_ts, entry_px, stop_px, target_px, side,
            timeout_bars=tf_timeout,
        )
        # Event-driven exit: HTF compass flip against the position.
        flip = bias_flip_exit(ticker, interval, entry_ts, side, timeout_bars=tf_timeout)

        if result is None and flip is None:
            continue
        # Choose the EARLIEST real exit. A pending "open_end" loses to any flip
        # but is otherwise "still open".
        candidates = []
        if result is not None and result[2] != "open_end":
            candidates.append(result)
        if flip is not None:
            candidates.append(flip)
        if not candidates:
            # Only open_end and no flip → genuinely still open.
            continue
        exit_ts, exit_px, reason = min(candidates, key=lambda r: r[0])

        evt = outcome_event(
            signal_id  = signal_id,
            exit_ts    = exit_ts.isoformat(),
            exit_px    = exit_px,
            exit_reason= reason,
        )
        append_jsonl(FORWARD_LOG, evt)
        closed += 1
        direction = 1 if side == "long" else -1
        ret_pct   = direction * (exit_px - entry_px) / entry_px * 100
        log.info(
            "ЗАКРЫТ %-6s %-5s  причина=%-7s выход=%.2f дох=%+.1f%%",
            ticker, side, reason, exit_px, ret_pct,
        )

    if closed:
        log.info("Закрыто сделок: %d", closed)
    return closed


# ─── ML retraining ──────────────────────────────────────────────────────────

def retrain_model() -> bool:
    """Rebuild dataset and retrain LightGBM. Returns True on success."""
    log.info("Переобучаю модель LightGBM …")
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

        log.info("Переобучение завершено. stdout: %s", r2.stdout[-300:])
        return True
    except Exception as e:
        log.error("Retrain failed: %s", e)
        return False


# ─── repair hallucinated exits ────────────────────────────────────────────────

def repair_outcomes() -> int:
    """Recompute every auto_trader exit from real history and rewrite the log.

    Fixes legacy outcomes that were closed at the live quote (months after the
    trade should have ended), which produced impossible exit prices. Manual /
    webhook trades are left untouched. Returns the number of outcomes rewritten.
    """
    events = read_jsonl(FORWARD_LOG)
    signals = {e["signal_id"]: e for e in events if e.get("event_type") == "signal"}
    auto_ids = {sid for sid, s in signals.items() if s.get("source") == "auto_trader"}

    fixed = 0
    new_events: list[dict] = []
    for e in events:
        # Drop old auto_trader outcomes; we recompute them below.
        if e.get("event_type") == "outcome" and e.get("signal_id") in auto_ids:
            continue
        new_events.append(e)

    for sid in auto_ids:
        s = signals[sid]
        tf = str(s.get("interval", "1d"))
        timeout = TIMEOUT_BY_TF.get(tf, TIMEOUT_BARS)
        result = historical_exit(
            s["ticker"], tf,
            pd.Timestamp(s["entry_ts"]), float(s["entry_px"]),
            float(s.get("stop_px") or 0), float(s.get("target_px") or 0),
            s.get("side", "long"),
            timeout_bars=timeout,
        )
        if result is None:
            log.warning("repair: no history for %s %s — left open", s["ticker"], sid)
            continue
        exit_ts, exit_px, reason = result
        if reason == "open_end":
            log.info("repair: %s %s still genuinely open", s["ticker"], sid)
            continue
        new_events.append(outcome_event(
            signal_id=sid, exit_ts=exit_ts.isoformat(),
            exit_px=exit_px, exit_reason=reason,
        ))
        fixed += 1
        direction = 1 if s.get("side") == "long" else -1
        ret_pct = direction * (exit_px - float(s["entry_px"])) / float(s["entry_px"]) * 100
        log.info("repair: %-6s %-5s reason=%-7s exit=%.4f ret=%+.1f%%",
                 s["ticker"], s.get("side"), reason, exit_px, ret_pct)

    FORWARD_LOG.write_text(
        "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in new_events),
        encoding="utf-8",
    )
    log.info("repair complete — %d outcome(s) rewritten", fixed)
    return fixed


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
    wl        = read_watchlist()
    tickers   = wl_all_tickers(wl)
    intervals = wl_intervals(wl)
    state     = read_state()

    crypto_count = sum(1 for t in tickers if is_crypto(t))
    stock_count  = len(tickers) - crypto_count

    all_tradeable_signals: list[dict] = []
    all_tradeable_set: set[str] = set()

    # Pre-compute session info per interval (fast, no I/O)
    interval_meta: dict[str, tuple[set[str], set[str]]] = {}
    for interval in intervals:
        tradeable, scan_only = split_by_session(tickers, interval)
        tradeable_set = set(t.upper() for t in tradeable)
        all_tradeable_set |= tradeable_set
        interval_meta[interval] = (tradeable_set, scan_only)
        log.info(
            "[%s] Сессия: крипто=%d(24/7) акции=%d(%s) — торгуемых=%d только_скан=%d",
            interval, crypto_count, stock_count,
            market_status(interval), len(tradeable), len(scan_only),
        )

    # Scan all intervals in parallel (each is an independent subprocess)
    def _scan_interval(interval: str) -> tuple[str, list[dict]]:
        signals = run_scan(tickers, interval)
        return interval, signals

    with ThreadPoolExecutor(max_workers=len(intervals)) as pool:
        futures = {pool.submit(_scan_interval, iv): iv for iv in intervals}
        for future in as_completed(futures):
            interval, signals = future.result()
            tradeable_set = interval_meta[interval][0]
            log.info("[%s] Скан вернул сигналов: %d", interval, len(signals))
            tradeable_signals = [s for s in signals if s.get("ticker", "").upper() in tradeable_set]
            if len(tradeable_signals) < len(signals):
                log.info("[%s] Отфильтровано торгуемых: %d", interval, len(tradeable_signals))
            all_tradeable_signals.extend(tradeable_signals)

    state["last_scan"] = utc_now_iso()

    # Open new trades across all intervals
    events = read_jsonl(FORWARD_LOG)
    opened = try_open_trades(all_tradeable_signals, events)

    # Close trades
    events = read_jsonl(FORWARD_LOG)
    closed = try_close_trades(events, all_tradeable_set)

    # Retrain if enough new closed trades
    state["closed_since_retrain"] = state.get("closed_since_retrain", 0) + closed
    if state["closed_since_retrain"] >= RETRAIN_EVERY:
        ok = retrain_model()
        if ok:
            state["closed_since_retrain"] = 0
            state["last_retrain"] = utc_now_iso()

    write_state(state)
    log.info(
        "Проход завершён — ТФ=%s открыто=%d закрыто=%d до_ретрейна=%d/%d",
        ",".join(intervals), opened, closed, state["closed_since_retrain"], RETRAIN_EVERY,
    )


def _acquire_single_instance_lock():
    """Non-blocking exclusive lock so an hourly cron pass never overlaps a still-
    running one (StartCalendarInterval :01 fires regardless of prior completion).
    Returns the open lock fd on success, or None if another pass holds it."""
    import fcntl
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd = open(LOCK_FILE, "w")
    try:
        fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fd.close()
        return None
    return fd


def main() -> None:
    parser = argparse.ArgumentParser(description="EWB autonomous paper trader")
    parser.add_argument("--once",   action="store_true", help="Single pass and exit")
    parser.add_argument("--status", action="store_true", help="Print status and exit")
    parser.add_argument("--repair", action="store_true",
                        help="Recompute all auto_trader exits from real history and exit")
    parser.add_argument("--interval", type=int, default=SCAN_INTERVAL,
                        help=f"Scan interval in seconds (default {SCAN_INTERVAL})")
    args = parser.parse_args()

    if args.status:
        print_status()
        return

    if args.repair:
        repair_outcomes()
        return

    if args.once:
        lock = _acquire_single_instance_lock()
        if lock is None:
            log.info("Предыдущий проход ещё идёт — пропускаю этот запуск (анти-наложение)")
            return
        try:
            one_pass()
        finally:
            lock.close()
        return

    log.info("Авто-трейдер запущен  scan_interval=%dс  trade_usd=$%.0f  min_p=%.0f%%  retrain_every=%d",
             args.interval, TRADE_USD, MIN_P_WIN * 100, RETRAIN_EVERY)
    while True:
        try:
            lock = _acquire_single_instance_lock()   # cooperate with the cron pass
            if lock is None:
                log.info("Проход уже идёт (cron?) — пропускаю итерацию")
            else:
                try:
                    one_pass()
                finally:
                    lock.close()
        except KeyboardInterrupt:
            log.info("Остановлено пользователем")
            break
        except Exception as e:
            log.exception("Unexpected error in pass: %s", e)
        log.info("Сон %dс до следующего скана …", args.interval)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
