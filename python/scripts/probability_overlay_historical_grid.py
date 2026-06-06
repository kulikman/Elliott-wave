"""Historical grid for EWB Probability Overlay v0.

This is a research parity script for `pine/ewb_probability_overlay_v0.pine`.
It mirrors the overlay's simplified pivot-window detector instead of the
Python monowave/Neely runtime used by `historical_signal_grid.py`.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import warnings
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

from ewb.htf import htf_bias_series, resample_ohlc
from ewb.research import cost_for, download_ohlc
from ewb.research.probability import load_probability_calibration, lookup_probability_row


REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CALIBRATION_PATH = os.path.join(
    REPO, "brain-output", "indicator-spec", "probability_calibration_v0.json"
)
OUT_MD = os.path.join(
    REPO, "docs", "validation", "probability_overlay_historical_grid_report.md"
)
OUT_JSON = os.path.join(
    REPO, "brain-output", "signals", "probability_overlay_historical_grid_summary.json"
)
OUT_TRADES = os.path.join(
    REPO, "python", "data", "probability_overlay_historical_grid_trades.parquet"
)
OHLC_CACHE_DIR = os.path.join(REPO, "python", "data", "ohlc_cache")
TIINGO_DELAY_SECONDS = 0.0
TIINGO_TIMEOUT_SECONDS = 45


class TiingoRateLimitError(RuntimeError):
    """Raised when Tiingo returns HTTP 429 so the run can checkpoint and stop."""


TOP100_STOCKS = [
    "NVDA", "MSFT", "AAPL", "AMZN", "GOOGL", "META", "AVGO", "TSLA", "BRK-B", "LLY",
    "JPM", "V", "NFLX", "MA", "XOM", "COST", "WMT", "ORCL", "UNH", "HD",
    "PG", "JNJ", "BAC", "ABBV", "KO", "PM", "TMUS", "CRM", "CSCO", "IBM",
    "CVX", "WFC", "ABT", "MCD", "GE", "MRK", "AXP", "ISRG", "MS", "NOW",
    "TMO", "DIS", "PEP", "GS", "AMD", "LIN", "ADBE", "QCOM", "INTU", "TXN",
    "UBER", "CAT", "AMGN", "VZ", "BKNG", "T", "SPGI", "PGR", "BLK", "DHR",
    "LOW", "NEE", "C", "RTX", "HON", "SYK", "PFE", "UNP", "SCHW", "AMAT",
    "TJX", "BSX", "ETN", "GILD", "CMCSA", "BA", "ADP", "PANW", "COP", "DE",
    "ANET", "LMT", "MU", "VRTX", "ADI", "MDT", "CB", "PLD", "MMC", "KLAC",
    "SBUX", "BMY", "NKE", "SO", "REGN", "ELV", "UPS", "FI", "ICE", "MO",
]

INTERVALS = {
    "15m": {"yf": "15m", "period": "60d", "htf": "1h", "source": "direct"},
    "30m": {"yf": "30m", "period": "60d", "htf": "1h", "source": "direct"},
    "1h": {"yf": "1h", "period": "730d", "htf": "4h", "source": "direct"},
    "4h": {"yf": "1h", "period": "730d", "htf": "1D", "source": "resample_4h"},
    "1d": {"yf": "1d", "period": "5y", "htf": "1W", "source": "direct"},
    "1w": {"yf": "1wk", "period": "10y", "htf": "1ME", "source": "direct"},
}
TIINGO_RESAMPLE = {
    "15m": "15min",
    "30m": "30min",
    "1h": "1hour",
    "1d": "daily",
    "1w": "weekly",
}

TRADE_PATTERNS = {"flat", "double_corr"}
RESEARCH_PATTERNS = {"impulse", "triangle"}
EXIT_BARS = {"flat": 20, "double_corr": 50, "impulse": 50, "triangle": 30}
ENTRY_VARIANTS = ("confirm_close", "next_open")
TP_MULTS = (0.5, 0.618, 1.0, 1.618)
SL_MULTS = (0.75, 1.0, 1.25)
LATE_LIMITS = (0.20, 0.35, 0.50, 999.0)
MTF_POLICIES = ("none", "warn", "pine_htf_not_against")
PROB_THRESHOLDS = (50, 52, 55, 58, 60, 65)
SAMPLE_THRESHOLDS = (0, 30, 50, 100)

LEFT_BARS = 5
RIGHT_BARS = 5
ATR_LEN = 14
MIN_AMP_ATR = 0.5
MAX_PIVOTS = 80


@dataclass(frozen=True)
class Pivot:
    bar: int
    confirm_idx: int
    price: float
    typ: int  # 1 high, -1 low


@dataclass(frozen=True)
class OverlaySignal:
    ticker: str
    interval: str
    universe_rank: int
    fig_type: str
    direction: str
    side: str
    mode: str
    pivot_end_bar: int
    confirm_idx: int
    amp: float
    pattern_start_idx: int
    pattern_end_idx: int


@dataclass(frozen=True)
class Entry:
    variant: str
    idx: int
    px: float
    ts: pd.Timestamp
    progress_to_tp: float


def pct(value: float | None, digits: int = 1) -> str:
    if value is None or not math.isfinite(float(value)):
        return "n/a"
    return f"{float(value) * 100:.{digits}f}%"


def num(value: float | None, digits: int = 2) -> str:
    if value is None or not math.isfinite(float(value)):
        return "n/a"
    return f"{float(value):.{digits}f}"


def money(value: float | None) -> str:
    if value is None or not math.isfinite(float(value)):
        return "n/a"
    return f"{float(value):,.0f}"


def side_int(side: str) -> int:
    return 1 if side == "long" else -1


def clean_timestamp(ts) -> str:
    return pd.Timestamp(ts).isoformat()


def normalize_utc_index(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    idx = pd.to_datetime(out.index)
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    else:
        idx = idx.tz_convert("UTC")
    out.index = idx
    return out


def period_start_date(period: str) -> str:
    unit = period[-1]
    amount = int(period[:-1])
    now = datetime.now(timezone.utc)
    if unit == "d":
        start = now - timedelta(days=amount)
    elif unit == "y":
        start = now - timedelta(days=amount * 365)
    else:
        start = now - timedelta(days=365)
    return start.date().isoformat()


def cache_path(provider: str, ticker: str, label: str, period: str) -> str:
    safe_ticker = ticker.replace("/", "-").replace(".", "-").replace(" ", "-")
    return os.path.join(OHLC_CACHE_DIR, provider, f"{safe_ticker}_{label}_{period}.parquet")


def read_ohlc_cache(provider: str, ticker: str, label: str, period: str) -> pd.DataFrame | None:
    path = cache_path(provider, ticker, label, period)
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_parquet(path)
    except Exception:
        return None
    if "date" in df.columns:
        df = df.set_index("date")
    return normalize_utc_index(df)


def write_ohlc_cache(provider: str, ticker: str, label: str, period: str, df: pd.DataFrame) -> None:
    path = cache_path(provider, ticker, label, period)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out = df.reset_index().rename(columns={df.index.name or "index": "date"})
    out.to_parquet(path, index=False)


def tiingo_request_json(
    url: str,
    params: dict[str, str],
    token: str,
    label: str,
    retries: int = 3,
) -> list[dict] | None:
    query = urllib.parse.urlencode({**params, "token": token})
    req = urllib.request.Request(
        f"{url}?{query}",
        headers={"Content-Type": "application/json", "Authorization": f"Token {token}"},
    )
    for attempt in range(retries):
        if TIINGO_DELAY_SECONDS > 0:
            time.sleep(TIINGO_DELAY_SECONDS)
        try:
            with urllib.request.urlopen(req, timeout=TIINGO_TIMEOUT_SECONDS) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            return payload if isinstance(payload, list) else None
        except urllib.error.HTTPError as exc:
            print(f"[tiingo] {label} HTTP {exc.code}")
            if exc.code == 429:
                raise TiingoRateLimitError(f"Tiingo rate limit reached at {label}")
            if exc.code in {401, 403, 404}:
                return None
            if attempt + 1 >= retries:
                return None
            time.sleep(2 ** attempt)
        except (urllib.error.URLError, TimeoutError):
            print(f"[tiingo] {label} network retry {attempt + 1}/{retries}")
            if attempt + 1 >= retries:
                return None
            time.sleep(2 ** attempt)
        except Exception as exc:
            print(f"[tiingo] {label} error {type(exc).__name__}")
            return None
    return None


def normalize_tiingo_rows(rows: list[dict], min_rows: int = 100) -> pd.DataFrame | None:
    if not rows:
        return None
    df = pd.DataFrame(rows)
    if df.empty or "date" not in df.columns:
        return None
    rename = {
        "adjOpen": "open",
        "adjHigh": "high",
        "adjLow": "low",
        "adjClose": "close",
        "adjVolume": "volume",
    }
    for src, dst in rename.items():
        if src in df.columns:
            df[dst] = df[src]
    base_cols = ["open", "high", "low", "close"]
    if not set(base_cols).issubset(df.columns):
        return None
    cols = base_cols + (["volume"] if "volume" in df.columns else [])
    out = df[["date", *cols]].copy()
    out["date"] = pd.to_datetime(out["date"], utc=True)
    out = out.set_index("date").sort_index()
    out = out[~out.index.duplicated(keep="last")]
    out = out.dropna(subset=base_cols)
    return out if len(out) > min_rows else None


def download_tiingo_ohlc(ticker: str, label: str, period: str, min_rows: int = 100) -> pd.DataFrame | None:
    cached = read_ohlc_cache("tiingo", ticker, label, period)
    if cached is not None and len(cached) > min_rows:
        return cached
    token = os.environ.get("TIINGO_API_KEY") or os.environ.get("TIINGO_TOKEN")
    if not token:
        raise RuntimeError("Set TIINGO_API_KEY or TIINGO_TOKEN before using --provider tiingo")

    symbol = ticker.lower()
    start_date = period_start_date(period)
    resample = TIINGO_RESAMPLE[label]
    if label in {"1d", "1w"}:
        url = f"https://api.tiingo.com/tiingo/daily/{urllib.parse.quote(symbol)}/prices"
        params = {"startDate": start_date, "resampleFreq": resample}
    else:
        url = f"https://api.tiingo.com/iex/{urllib.parse.quote(symbol)}/prices"
        params = {"startDate": start_date, "resampleFreq": resample}
    rows = tiingo_request_json(url, params, token, f"{ticker} {label}")
    df = normalize_tiingo_rows(rows or [], min_rows=min_rows)
    if df is not None:
        write_ohlc_cache("tiingo", ticker, label, period, df)
    return df


def download_provider_ohlc(
    ticker: str,
    label: str,
    interval: str,
    period: str,
    provider: str,
    min_rows: int = 100,
) -> pd.DataFrame | None:
    if provider == "tiingo":
        return download_tiingo_ohlc(ticker, label, period, min_rows=min_rows)
    return download_ohlc(ticker, interval, period, min_rows=min_rows)


def load_frame(
    ticker: str,
    label: str,
    cache_1h: dict[str, pd.DataFrame | None],
    provider: str,
) -> pd.DataFrame | None:
    cfg = INTERVALS[label]
    if cfg["source"] == "resample_4h":
        raw = cache_1h.get(ticker)
        if raw is None:
            raw = download_provider_ohlc(ticker, "1h", "1h", "730d", provider, min_rows=100)
            if raw is not None:
                raw = normalize_utc_index(raw)
            cache_1h[ticker] = raw
        return resample_ohlc(raw, "4h") if raw is not None else None
    df = download_provider_ohlc(ticker, label, cfg["yf"], cfg["period"], provider, min_rows=100)
    if df is not None:
        df = normalize_utc_index(df)
    if label == "1h":
        cache_1h[ticker] = df
    return df


def atr_rma(df: pd.DataFrame, length: int = ATR_LEN) -> np.ndarray:
    high = df["high"].to_numpy(float)
    low = df["low"].to_numpy(float)
    close = df["close"].to_numpy(float)
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))
    return pd.Series(tr, index=df.index).ewm(alpha=1 / length, adjust=False).mean().to_numpy(float)


def pivot_high(high: np.ndarray, p: int, left: int, right: int) -> bool:
    if p < left or p + right >= len(high):
        return False
    value = high[p]
    window = high[p - left:p + right + 1]
    return bool(np.isfinite(value) and value >= np.nanmax(window))


def pivot_low(low: np.ndarray, p: int, left: int, right: int) -> bool:
    if p < left or p + right >= len(low):
        return False
    value = low[p]
    window = low[p - left:p + right + 1]
    return bool(np.isfinite(value) and value <= np.nanmin(window))


def push_pivot(pivots: list[Pivot], pivot: Pivot) -> None:
    if not pivots:
        pivots.append(pivot)
        return
    last = pivots[-1]
    if pivot.typ == last.typ:
        more_extreme = pivot.price > last.price if pivot.typ == 1 else pivot.price < last.price
        if more_extreme:
            pivots[-1] = pivot
    else:
        pivots.append(pivot)
    while len(pivots) > MAX_PIVOTS:
        pivots.pop(0)


def alternate_from(pivots: list[Pivot], start: int, waves: int) -> bool:
    for i in range(start + 1, start + waves + 1):
        if pivots[i].typ == pivots[i - 1].typ:
            return False
    return True


def fig_direction(pivots: list[Pivot], start: int) -> str:
    return "up" if pivots[start + 1].price > pivots[start].price else "down"


def flat_ok(pivots: list[Pivot], start: int) -> bool:
    a = abs(pivots[start + 1].price - pivots[start].price)
    b = abs(pivots[start + 2].price - pivots[start + 1].price)
    return a > 0 and b / a >= 0.618


def double_corr_ok(pivots: list[Pivot], start: int) -> bool:
    w = abs(pivots[start + 1].price - pivots[start].price)
    x = abs(pivots[start + 2].price - pivots[start + 1].price)
    xr = x / w if w > 0 else np.nan
    return bool(np.isfinite(xr) and xr > 0.1 and xr < 0.618)


def impulse_ok(pivots: list[Pivot], start: int) -> bool:
    p0 = pivots[start].price
    p1 = pivots[start + 1].price
    p2 = pivots[start + 2].price
    p3 = pivots[start + 3].price
    w1 = abs(p1 - p0)
    w2 = abs(p2 - p1)
    w3 = abs(p3 - p2)
    up = p1 > p0
    w2_no_start_break = p2 > p0 if up else p2 < p0
    w3_not_short = w3 >= w1
    w2_shallow = w2 / w1 <= 0.618 if w1 > 0 else False
    return bool(w2_no_start_break and w3_not_short and w2_shallow)


def triangle_ok(pivots: list[Pivot], start: int) -> bool:
    w1 = abs(pivots[start + 1].price - pivots[start].price)
    w2 = abs(pivots[start + 2].price - pivots[start + 1].price)
    w3 = abs(pivots[start + 3].price - pivots[start + 2].price)
    w4 = abs(pivots[start + 4].price - pivots[start + 3].price)
    return bool(w3 < w1 and w4 < w2)


def side_for(fig_type: str, direction: str) -> tuple[str, str]:
    if fig_type in TRADE_PATTERNS:
        return "fade", "short" if direction == "up" else "long"
    if fig_type == "impulse":
        return "follow_research", "long" if direction == "up" else "short"
    return "context_research", "short" if direction == "up" else "long"


def detect_overlay_signals(
    ticker: str,
    interval: str,
    universe_rank: int,
    df: pd.DataFrame,
) -> list[OverlaySignal]:
    high = df["high"].to_numpy(float)
    low = df["low"].to_numpy(float)
    atr = atr_rma(df)
    pivots: list[Pivot] = []
    last_signal_pivot_bar: int | None = None
    out: list[OverlaySignal] = []

    def try_detect(current_idx: int) -> None:
        nonlocal last_signal_pivot_bar
        n = len(pivots)
        if n >= 4:
            s4 = n - 4
            end_bar4 = pivots[-1].bar
            new_window4 = last_signal_pivot_bar is None or end_bar4 != last_signal_pivot_bar
            amp4 = abs(pivots[s4 + 3].price - pivots[s4].price)
            min_amp = atr[current_idx] * MIN_AMP_ATR
            if new_window4 and alternate_from(pivots, s4, 3) and amp4 >= min_amp:
                direction = fig_direction(pivots, s4)
                fig_type = ""
                if flat_ok(pivots, s4):
                    fig_type = "flat"
                elif double_corr_ok(pivots, s4):
                    fig_type = "double_corr"
                if fig_type:
                    mode, side = side_for(fig_type, direction)
                    out.append(OverlaySignal(
                        ticker=ticker,
                        interval=interval,
                        universe_rank=universe_rank,
                        fig_type=fig_type,
                        direction=direction,
                        side=side,
                        mode=mode,
                        pivot_end_bar=end_bar4,
                        confirm_idx=current_idx,
                        amp=float(amp4),
                        pattern_start_idx=pivots[s4].bar,
                        pattern_end_idx=end_bar4,
                    ))
                    last_signal_pivot_bar = end_bar4
        n = len(pivots)
        if n >= 6:
            s6 = n - 6
            end_bar6 = pivots[-1].bar
            new_window6 = last_signal_pivot_bar is None or end_bar6 != last_signal_pivot_bar
            if new_window6 and alternate_from(pivots, s6, 5):
                fig_type = ""
                if impulse_ok(pivots, s6):
                    fig_type = "impulse"
                elif triangle_ok(pivots, s6):
                    fig_type = "triangle"
                if fig_type:
                    direction = fig_direction(pivots, s6)
                    mode, side = side_for(fig_type, direction)
                    amp = abs(pivots[s6 + 5].price - pivots[s6].price)
                    out.append(OverlaySignal(
                        ticker=ticker,
                        interval=interval,
                        universe_rank=universe_rank,
                        fig_type=fig_type,
                        direction=direction,
                        side=side,
                        mode=mode,
                        pivot_end_bar=end_bar6,
                        confirm_idx=current_idx,
                        amp=float(amp),
                        pattern_start_idx=pivots[s6].bar,
                        pattern_end_idx=end_bar6,
                    ))
                    last_signal_pivot_bar = end_bar6

    for current_idx in range(len(df)):
        pivot_idx = current_idx - RIGHT_BARS
        if pivot_idx < 0:
            continue
        if pivot_high(high, pivot_idx, LEFT_BARS, RIGHT_BARS):
            push_pivot(pivots, Pivot(pivot_idx, current_idx, float(high[pivot_idx]), 1))
            try_detect(current_idx)
        if pivot_low(low, pivot_idx, LEFT_BARS, RIGHT_BARS):
            push_pivot(pivots, Pivot(pivot_idx, current_idx, float(low[pivot_idx]), -1))
            try_detect(current_idx)
    return out


def entry_variants(df: pd.DataFrame, signal: OverlaySignal) -> list[Entry]:
    if signal.confirm_idx < 0 or signal.confirm_idx >= len(df):
        return []
    close = df["close"].to_numpy(float)
    open_ = df["open"].to_numpy(float)
    entry_px = float(close[signal.confirm_idx])
    out = [Entry("confirm_close", signal.confirm_idx, entry_px, df.index[signal.confirm_idx], 0.0)]
    next_idx = signal.confirm_idx + 1
    if next_idx < len(df) and signal.amp > 0:
        sign = side_int(signal.side)
        progress = sign * (float(open_[next_idx]) - entry_px) / signal.amp
        out.append(Entry("next_open", next_idx, float(open_[next_idx]), df.index[next_idx], progress))
    return out


def simulate_full_exit(
    df: pd.DataFrame,
    entry: Entry,
    side: str,
    amp: float,
    exit_bars: int,
    tp_mult: float,
    sl_mult: float,
    cost: float,
) -> dict | None:
    high = df["high"].to_numpy(float)
    low = df["low"].to_numpy(float)
    close = df["close"].to_numpy(float)
    sign = side_int(side)
    if amp <= 0 or entry.idx + 1 >= len(df):
        return None
    tp = entry.px + sign * amp * tp_mult
    sl = entry.px - sign * amp * sl_mult
    last_idx = min(entry.idx + exit_bars, len(df) - 1)
    exit_idx = last_idx
    exit_px = float(close[last_idx])
    reason = "time"
    for idx in range(entry.idx + 1, last_idx + 1):
        hi = float(high[idx])
        lo = float(low[idx])
        if side == "long":
            if lo <= sl:
                exit_idx, exit_px, reason = idx, sl, "sl"
                break
            if hi >= tp:
                exit_idx, exit_px, reason = idx, tp, "tp"
                break
        else:
            if hi >= sl:
                exit_idx, exit_px, reason = idx, sl, "sl"
                break
            if lo <= tp:
                exit_idx, exit_px, reason = idx, tp, "tp"
                break
    raw_ret = sign * (exit_px - entry.px) / entry.px
    net_ret = raw_ret - 2 * cost
    return {
        "exit_idx": int(exit_idx),
        "exit_ts": df.index[exit_idx],
        "exit_px": float(exit_px),
        "bars_held": int(exit_idx - entry.idx),
        "raw_ret": float(raw_ret),
        "net_ret": float(net_ret),
        "win": bool(net_ret > 0),
        "exit_reason": reason,
    }


def simulate_partial_exit(
    df: pd.DataFrame,
    entry: Entry,
    side: str,
    amp: float,
    exit_bars: int,
    sl_mult: float,
    cost: float,
) -> dict | None:
    high = df["high"].to_numpy(float)
    low = df["low"].to_numpy(float)
    close = df["close"].to_numpy(float)
    sign = side_int(side)
    if amp <= 0 or entry.idx + 1 >= len(df):
        return None
    levels = [0.5, 1.0, 1.618]
    remaining = 1.0
    realized = 0.0
    next_tp = 0
    sl = entry.px - sign * amp * sl_mult
    last_idx = min(entry.idx + exit_bars, len(df) - 1)
    exit_idx = last_idx
    reason = "time"
    for idx in range(entry.idx + 1, last_idx + 1):
        hi = float(high[idx])
        lo = float(low[idx])
        sl_hit = lo <= sl if side == "long" else hi >= sl
        if sl_hit:
            raw = sign * (sl - entry.px) / entry.px
            realized += remaining * raw
            remaining = 0.0
            exit_idx = idx
            reason = "sl"
            break
        while next_tp < len(levels):
            tp = entry.px + sign * amp * levels[next_tp]
            tp_hit = hi >= tp if side == "long" else lo <= tp
            if not tp_hit:
                break
            weight = 1.0 / len(levels)
            raw = sign * (tp - entry.px) / entry.px
            realized += weight * raw
            remaining -= weight
            next_tp += 1
            exit_idx = idx
            reason = f"tp{next_tp}"
        if remaining <= 1e-9:
            break
    if remaining > 1e-9:
        raw = sign * (float(close[last_idx]) - entry.px) / entry.px
        realized += remaining * raw
        exit_idx = max(exit_idx, last_idx)
        if reason.startswith("tp"):
            reason = "partial_time"
    net_ret = realized - 2 * cost
    return {
        "exit_idx": int(exit_idx),
        "exit_ts": df.index[exit_idx],
        "exit_px": float(close[exit_idx]),
        "bars_held": int(exit_idx - entry.idx),
        "raw_ret": float(realized),
        "net_ret": float(net_ret),
        "win": bool(net_ret > 0),
        "exit_reason": reason,
    }


def mtf_allowed(policy: str, side: str, bias: int) -> bool:
    if policy in {"none", "warn"}:
        return True
    if policy == "pine_htf_not_against":
        return bias >= 0 if side == "long" else bias <= 0
    return True


def probability_meta(calibration: dict, fig_type: str, interval: str, side: str) -> dict:
    row = lookup_probability_row(calibration, fig_type, interval, side)
    if row is None:
        return {
            "p_win_model": np.nan,
            "sample_size": 0,
            "model_confidence": "unknown",
            "model_ev": np.nan,
            "lookup_key": "",
            "lookup_level": "",
        }
    return {
        "p_win_model": float(row.get("p_trade_win") or np.nan) * 100,
        "sample_size": int(row.get("n") or 0),
        "model_confidence": row.get("confidence", "unknown"),
        "model_ev": float(row.get("expected_net_return") or np.nan),
        "lookup_key": row.get("key", ""),
        "lookup_level": row.get("level", ""),
    }


def build_trades_for_frame(
    ticker: str,
    label: str,
    rank: int,
    df: pd.DataFrame,
    calibration: dict,
) -> list[dict]:
    signals = detect_overlay_signals(ticker, label, rank, df)
    bias_series = htf_bias_series(df, INTERVALS[label]["htf"])
    cost = cost_for(ticker)
    rows: list[dict] = []
    for signal in signals:
        if signal.confirm_idx + 2 >= len(df) or signal.amp <= 0:
            continue
        pmeta = probability_meta(calibration, signal.fig_type, label, signal.side)
        htf_bias = int(bias_series.iloc[signal.confirm_idx]) if signal.confirm_idx < len(bias_series) else 0
        policies = MTF_POLICIES if signal.fig_type in TRADE_PATTERNS else ("none",)
        entries = entry_variants(df, signal)
        if signal.fig_type in RESEARCH_PATTERNS:
            entries = [entry for entry in entries if entry.variant == "confirm_close"]
        for policy in policies:
            if not mtf_allowed(policy, signal.side, htf_bias):
                continue
            for entry in entries:
                late_limits = LATE_LIMITS if entry.variant == "next_open" else (999.0,)
                for late_limit in late_limits:
                    if entry.progress_to_tp > late_limit:
                        continue
                    tp_values = TP_MULTS if signal.fig_type in TRADE_PATTERNS else (1.0,)
                    sl_values = SL_MULTS if signal.fig_type in TRADE_PATTERNS else (1.0,)
                    for tp_mult in tp_values:
                        for sl_mult in sl_values:
                            result = simulate_full_exit(
                                df,
                                entry,
                                signal.side,
                                signal.amp,
                                EXIT_BARS[signal.fig_type],
                                tp_mult,
                                sl_mult,
                                cost,
                            )
                            if result is None:
                                continue
                            rows.append({
                                **base_record(signal, policy, entry, late_limit, tp_mult, sl_mult, "full", htf_bias, pmeta),
                                **result,
                            })
                    if signal.fig_type not in TRADE_PATTERNS:
                        continue
                    for sl_mult in SL_MULTS:
                        result = simulate_partial_exit(
                            df,
                            entry,
                            signal.side,
                            signal.amp,
                            EXIT_BARS[signal.fig_type],
                            sl_mult,
                            cost,
                        )
                        if result is None:
                            continue
                        rows.append({
                            **base_record(
                                signal, policy, entry, late_limit, 1.618, sl_mult,
                                "partial_50_100_1618", htf_bias, pmeta
                            ),
                            **result,
                        })
    return rows


def base_record(
    signal: OverlaySignal,
    mtf_policy: str,
    entry: Entry,
    late_limit: float,
    tp_mult: float,
    sl_mult: float,
    exit_plan: str,
    htf_bias: int,
    pmeta: dict,
) -> dict:
    return {
        "ticker": signal.ticker,
        "indicator": "probability_overlay_v0",
        "asset_class": "stocks",
        "universe_rank": signal.universe_rank,
        "interval": signal.interval,
        "fig_type": signal.fig_type,
        "mode": signal.mode,
        "direction": signal.direction,
        "side": signal.side,
        "mtf_policy": mtf_policy,
        "htf_bias": htf_bias,
        "entry_variant": entry.variant,
        "entry_idx": int(entry.idx),
        "entry_ts": entry.ts,
        "entry_px": float(entry.px),
        "progress_to_tp": float(entry.progress_to_tp),
        "late_limit": float(late_limit),
        "tp_mult": float(tp_mult),
        "sl_mult": float(sl_mult),
        "exit_plan": exit_plan,
        "amp_pct": float(signal.amp / entry.px),
        "pattern_start_idx": int(signal.pattern_start_idx),
        "pattern_end_idx": int(signal.pattern_end_idx),
        "confirm_idx": int(signal.confirm_idx),
        "confirmation_lag": int(signal.confirm_idx - signal.pattern_end_idx),
        **pmeta,
    }


def profit_factor(returns: pd.Series) -> float:
    wins = returns[returns > 0].sum()
    losses = returns[returns < 0].sum()
    if losses == 0:
        return np.inf if wins > 0 else np.nan
    return float(wins / abs(losses))


def max_drawdown(returns: pd.Series) -> float:
    if returns.empty:
        return np.nan
    eq = (1.0 + returns).cumprod()
    peak = eq.cummax()
    return float((eq / peak - 1.0).min())


def metric_row(df: pd.DataFrame) -> dict:
    if df.empty:
        return {}
    returns = df["net_ret"].astype(float)
    return {
        "trades": int(len(df)),
        "winrate": float((returns > 0).mean()),
        "ev": float(returns.mean()),
        "median_return": float(returns.median()),
        "profit_factor": profit_factor(returns),
        "max_drawdown": max_drawdown(returns),
        "avg_holding_bars": float(df["bars_held"].mean()),
        "tp_rate": float(df["exit_reason"].astype(str).str.startswith("tp").mean()),
        "sl_rate": float((df["exit_reason"] == "sl").mean()),
        "time_rate": float(df["exit_reason"].astype(str).str.contains("time").mean()),
    }


def split_metrics(df: pd.DataFrame) -> dict:
    ordered = df.sort_values("entry_ts").reset_index(drop=True)
    n = len(ordered)
    if n == 0:
        return {}
    train = ordered.iloc[: int(n * 0.60)]
    val = ordered.iloc[int(n * 0.60): int(n * 0.80)]
    test = ordered.iloc[int(n * 0.80):]
    return {
        "train": metric_row(train),
        "validation": metric_row(val),
        "test": metric_row(test),
    }


def walk_forward_metrics(df: pd.DataFrame, folds: int = 5) -> dict:
    ordered = df.sort_values("entry_ts").reset_index(drop=True)
    n = len(ordered)
    rows = []
    for fold in range(folds):
        sub = ordered.iloc[fold * n // folds: (fold + 1) * n // folds]
        if sub.empty:
            continue
        m = metric_row(sub)
        rows.append({
            "fold": fold + 1,
            "start": clean_timestamp(sub.iloc[0]["entry_ts"]),
            "end": clean_timestamp(sub.iloc[-1]["entry_ts"]),
            **m,
        })
    if not rows:
        return {"folds": [], "positive_ev_folds": 0, "winrate_std": np.nan, "ev_std": np.nan}
    return {
        "folds": rows,
        "positive_ev_folds": int(sum(1 for row in rows if row.get("ev", 0) > 0)),
        "winrate_std": float(np.std([row["winrate"] for row in rows], ddof=0)),
        "ev_std": float(np.std([row["ev"] for row in rows], ddof=0)),
    }


def confidence_label(row: dict) -> str:
    n = row.get("trades", 0)
    pf = row.get("profit_factor", np.nan)
    dd = abs(row.get("max_drawdown", 0) or 0)
    folds = row.get("positive_ev_folds", 0)
    if n >= 50 and pf >= 1.5 and dd <= 0.20 and folds >= 4:
        return "high"
    if n >= 30 and pf >= 1.2 and dd <= 0.30 and folds >= 3:
        return "medium"
    return "low"


def score_balanced(row: dict) -> float:
    n = row.get("trades", 0)
    win = row.get("winrate", 0)
    ev = row.get("ev", 0)
    pf = row.get("profit_factor", 0)
    dd = abs(row.get("max_drawdown", 0) or 0)
    folds = row.get("positive_ev_folds", 0)
    sample_bonus = min(math.log(max(n, 1), 10) / 2.0, 1.0)
    pf_term = 0 if not math.isfinite(pf) else min(pf / 3.0, 1.5)
    return float(win + 30 * ev + 0.25 * pf_term + 0.15 * folds / 5 + 0.1 * sample_bonus - dd)


def aggregate_setups(trades: pd.DataFrame, universe_limit: int) -> pd.DataFrame:
    scoped = trades[trades["universe_rank"] <= universe_limit].copy()
    scoped["entry_ts"] = pd.to_datetime(scoped["entry_ts"], utc=True)
    groups = [
        "interval", "fig_type", "side", "mode", "mtf_policy", "entry_variant",
        "late_limit", "tp_mult", "sl_mult", "exit_plan",
    ]
    rows = []
    for key, grp in scoped.groupby(groups, dropna=False):
        if len(grp) < 5:
            continue
        m = metric_row(grp)
        if not m:
            continue
        split = split_metrics(grp)
        wf = walk_forward_metrics(grp) if len(grp) >= 30 else {
            "positive_ev_folds": 0,
            "winrate_std": np.nan,
            "ev_std": np.nan,
        }
        row = dict(zip(groups, key))
        row.update(m)
        row.update({
            "universe": f"top{universe_limit}",
            "p_win_model": float(grp["p_win_model"].dropna().mean()) if grp["p_win_model"].notna().any() else np.nan,
            "sample_size": int(grp["sample_size"].dropna().median()) if grp["sample_size"].notna().any() else 0,
            "model_confidence": str(grp["model_confidence"].mode().iloc[0]) if not grp["model_confidence"].empty else "unknown",
            "train_winrate": split.get("train", {}).get("winrate", np.nan),
            "validation_winrate": split.get("validation", {}).get("winrate", np.nan),
            "test_winrate": split.get("test", {}).get("winrate", np.nan),
            "train_ev": split.get("train", {}).get("ev", np.nan),
            "validation_ev": split.get("validation", {}).get("ev", np.nan),
            "test_ev": split.get("test", {}).get("ev", np.nan),
            "positive_ev_folds": wf.get("positive_ev_folds", 0),
            "winrate_std": wf.get("winrate_std", np.nan),
            "ev_std": wf.get("ev_std", np.nan),
        })
        row["confidence"] = confidence_label(row)
        row["balanced_score"] = score_balanced(row)
        rows.append(row)
    return pd.DataFrame(rows)


def portfolio_metrics(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"n": 0}
    ordered = df.sort_values("entry_ts").reset_index(drop=True)
    returns = ordered["net_ret"].astype(float)
    start = pd.to_datetime(ordered["entry_ts"]).min()
    end = pd.to_datetime(ordered["exit_ts"]).max()
    years = max((end - start).total_seconds() / (365.25 * 24 * 3600), 1 / 365.25)
    eq = (1 + returns).cumprod()
    final = float(100000 * eq.iloc[-1])
    cagr = float((final / 100000) ** (1 / years) - 1)
    sharpe = float(returns.mean() / returns.std(ddof=0) * math.sqrt(len(returns))) if returns.std(ddof=0) > 0 else np.nan
    return {
        "n": int(len(ordered)),
        "final": final,
        "cagr": cagr,
        "sharpe": sharpe,
        "dd": max_drawdown(returns),
        "win": float((returns > 0).mean()),
        "ev": float(returns.mean()),
        "years": years,
    }


def default_slice(trades: pd.DataFrame, universe_limit: int) -> pd.DataFrame:
    return trades[
        (trades["universe_rank"] <= universe_limit)
        & (trades["entry_variant"] == "confirm_close")
        & (trades["late_limit"] == 999.0)
        & (trades["tp_mult"] == 1.0)
        & (trades["sl_mult"] == 1.0)
        & (trades["exit_plan"] == "full")
    ].copy()


def requested_rows(trades: pd.DataFrame, universe_limit: int) -> list[dict]:
    base = default_slice(trades, universe_limit)
    specs = [
        ("Flat+DC all TF / no HTF", lambda d: d.fig_type.isin(["flat", "double_corr"]) & (d.mtf_policy == "none")),
        ("Flat+DC all TF / Pine HTF", lambda d: d.fig_type.isin(["flat", "double_corr"]) & (d.mtf_policy == "pine_htf_not_against")),
        ("DoubleCorr 1h+4h / no HTF", lambda d: (d.fig_type == "double_corr") & d.interval.isin(["1h", "4h"]) & (d.mtf_policy == "none")),
        ("Flat baseline", lambda d: (d.fig_type == "flat") & (d.mtf_policy == "none")),
        ("Flat 1h long", lambda d: (d.fig_type == "flat") & (d.interval == "1h") & (d.side == "long") & (d.mtf_policy == "none")),
        ("Flat 1h short", lambda d: (d.fig_type == "flat") & (d.interval == "1h") & (d.side == "short") & (d.mtf_policy == "none")),
        ("Impulse/Triangle research", lambda d: d.fig_type.isin(["impulse", "triangle"])),
    ]
    out = []
    for name, mask_fn in specs:
        sub = base[mask_fn(base)]
        m = portfolio_metrics(sub)
        out.append({"universe": f"top{universe_limit}", "slice": name, **m})
    return out


def mtf_breakdown_rows(trades: pd.DataFrame, universe_limit: int) -> list[dict]:
    base = default_slice(trades, universe_limit)
    base = base[base["fig_type"].isin(["flat", "double_corr"])]
    rows = []
    for (interval, policy), grp in base.groupby(["interval", "mtf_policy"]):
        m = metric_row(grp)
        rows.append({
            "universe": f"top{universe_limit}",
            "interval": interval,
            "mtf_policy": policy,
            **m,
        })
    return rows


def probability_filter_rows(trades: pd.DataFrame, universe_limit: int) -> pd.DataFrame:
    base = default_slice(trades, universe_limit)
    base = base[base["fig_type"].isin(["flat", "double_corr"])]
    rows = []
    for min_p in PROB_THRESHOLDS:
        for min_n in SAMPLE_THRESHOLDS:
            for no_low in (False, True):
                sub = base[
                    (base["p_win_model"].fillna(0) >= min_p)
                    & (base["sample_size"].fillna(0) >= min_n)
                ]
                if no_low:
                    sub = sub[sub["model_confidence"] != "low"]
                if len(sub) < 5:
                    continue
                m = metric_row(sub)
                rows.append({
                    "universe": f"top{universe_limit}",
                    "min_p": min_p,
                    "min_n": min_n,
                    "no_low": no_low,
                    **m,
                })
    return pd.DataFrame(rows)


def write_trades_frame(df: pd.DataFrame, path: str) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        tmp_path = path.replace(".parquet", "_tmp.parquet")
        df.to_parquet(tmp_path, index=False)
        os.replace(tmp_path, path)
        csv_path = path.replace(".parquet", ".csv")
        if os.path.exists(csv_path):
            os.remove(csv_path)
        return path
    except Exception:
        csv_path = path.replace(".parquet", ".csv")
        df.to_csv(csv_path, index=False)
        return csv_path


def read_checkpoint(path: str) -> pd.DataFrame | None:
    if os.path.exists(path):
        return pd.read_parquet(path)
    csv_path = path.replace(".parquet", ".csv")
    if os.path.exists(csv_path):
        return pd.read_csv(csv_path)
    return None


def write_checkpoint(rows: list[dict], path: str) -> None:
    if not rows:
        return
    write_trades_frame(pd.DataFrame(rows), path)


def format_table(rows: Iterable[dict], columns: list[tuple[str, str]], limit: int | None = None) -> list[str]:
    rows = list(rows)
    if limit is not None:
        rows = rows[:limit]
    header = "| " + " | ".join(label for label, _ in columns) + " |"
    sep = "| " + " | ".join("---" for _ in columns) + " |"
    out = [header, sep]
    for row in rows:
        vals = []
        for _, key in columns:
            val = row.get(key)
            if key in {
                "winrate", "ev", "median_return", "max_drawdown", "tp_rate", "sl_rate",
                "time_rate", "test_winrate", "test_ev", "cagr", "dd", "win",
            }:
                vals.append(pct(val))
            elif key in {"profit_factor", "pf", "sharpe", "avg_holding_bars", "years"}:
                vals.append(num(val))
            elif key == "final":
                vals.append("$" + money(val))
            elif key == "late_limit":
                vals.append("off" if val == 999.0 else pct(val, 0))
            elif key in {"tp_mult", "sl_mult"}:
                vals.append(num(val, 3))
            elif key in {"trades", "n", "sample_size", "positive_ev_folds"}:
                vals.append(str(int(val)) if val is not None and pd.notna(val) else "0")
            else:
                vals.append(str(val))
        out.append("| " + " | ".join(vals) + " |")
    return out


def json_safe(value):
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float):
        if math.isinf(value):
            return "inf" if value > 0 else "-inf"
        if math.isnan(value):
            return None
    return value


def write_report(summary: dict, trades: pd.DataFrame, setup_rows: pd.DataFrame, prob_rows: pd.DataFrame) -> None:
    best_winrate = setup_rows[
        (setup_rows["fig_type"].isin(["flat", "double_corr"]))
        & (setup_rows["trades"] >= 20)
    ].sort_values(["winrate", "trades"], ascending=[False, False]).head(15)
    best_balanced = setup_rows[
        (setup_rows["fig_type"].isin(["flat", "double_corr"]))
        & (setup_rows["trades"] >= 20)
        & (setup_rows["ev"] > 0)
    ].sort_values("balanced_score", ascending=False).head(15)
    disable_rows = setup_rows[
        (setup_rows["fig_type"].isin(["flat", "double_corr"]))
        & (setup_rows["trades"] >= 20)
        & ((setup_rows["ev"] < 0) | (setup_rows["profit_factor"] < 1.0))
    ].sort_values(["ev", "winrate"], ascending=[True, True]).head(12)
    research_rows = setup_rows[
        (setup_rows["fig_type"].isin(["impulse", "triangle"]))
        & (setup_rows["trades"] >= 20)
    ].sort_values(["balanced_score"], ascending=False).head(12)

    setup_cols = [
        ("Universe", "universe"), ("TF", "interval"), ("Pattern", "fig_type"),
        ("Side", "side"), ("MTF", "mtf_policy"), ("Entry", "entry_variant"),
        ("Late", "late_limit"), ("TP", "tp_mult"), ("SL", "sl_mult"),
        ("Exit", "exit_plan"), ("Trades", "trades"), ("Win", "winrate"),
        ("EV", "ev"), ("Test win", "test_winrate"), ("Test EV", "test_ev"),
        ("DD", "max_drawdown"), ("PF", "profit_factor"), ("Conf", "confidence"),
    ]
    requested_cols = [
        ("Universe", "universe"), ("Slice", "slice"), ("Trades", "n"), ("Win", "win"),
        ("EV", "ev"), ("CAGR", "cagr"), ("Sharpe", "sharpe"), ("DD", "dd"),
        ("Final", "final"),
    ]
    mtf_cols = [
        ("Universe", "universe"), ("TF", "interval"), ("MTF", "mtf_policy"),
        ("Trades", "trades"), ("Win", "winrate"), ("EV", "ev"), ("DD", "max_drawdown"),
        ("PF", "profit_factor"), ("TP", "tp_rate"), ("SL", "sl_rate"),
    ]
    prob_cols = [
        ("Universe", "universe"), ("Min P", "min_p"), ("Min N", "min_n"),
        ("No low", "no_low"), ("Trades", "trades"), ("Win", "winrate"),
        ("EV", "ev"), ("DD", "max_drawdown"), ("PF", "profit_factor"),
    ]

    lines = [
        "# Probability Overlay v0 Historical Grid",
        "",
        f"Generated: `{summary['generated_at']}`",
        "",
        "Scope: stocks only. This mirrors the simplified `EWB — Probability Overlay v0` pivot-window detector, not the full Monowaves MTF runtime.",
        "",
        "## Run scope",
        "",
        f"- Data provider: `{summary['data_provider']}`.",
        f"- Requested universe modes: top20/top100; executed max rank: `{summary['max_universe_rank']}`.",
        f"- Tickers with usable data: `{summary['tickers_ok']}` / `{summary['tickers_requested']}`.",
        f"- Base simulated rows after variants: `{summary['trade_rows']}`.",
        f"- Timeframes: `{', '.join(summary['intervals'])}`.",
        f"- Pivot settings: left={LEFT_BARS}, right={RIGHT_BARS}, min amplitude={MIN_AMP_ATR} ATR.",
        "",
        "## Requested comparison slices",
        "",
        *format_table(summary["requested_rows"], requested_cols),
        "",
        "## MTF breakdown for Flat/DC default contract",
        "",
        *format_table(summary["mtf_breakdown"], mtf_cols),
        "",
        "## Best winrate setups",
        "",
        *format_table(best_winrate.to_dict("records"), setup_cols, limit=15),
        "",
        "## Best balanced setups",
        "",
        *format_table(best_balanced.to_dict("records"), setup_cols, limit=15),
        "",
        "## Setups to disable or keep as WAIT/research",
        "",
        *format_table(disable_rows.to_dict("records"), setup_cols, limit=12),
        "",
        "## Impulse/Triangle research check",
        "",
        *format_table(research_rows.to_dict("records"), setup_cols, limit=12),
        "",
        "## Probability filter observations",
        "",
        *format_table(
            prob_rows.sort_values(["winrate", "trades"], ascending=[False, False]).head(12).to_dict("records"),
            prob_cols,
        ),
        "",
        "## Notes",
        "",
        "- `Pine HTF` here is an external Python HTF filter applied to overlay signals; the overlay itself does not draw MTF monowaves.",
        "- Use this report to compare overlay detector quality with `historical_signal_grid_report.md`; do not merge the two signal sources blindly.",
        "- Rows with very high winrate and small sample still need out-of-sample/manual parity before becoming TradingView defaults.",
        "",
        "## Files",
        "",
        f"- Trades: `{summary['outputs']['trades']}`",
        f"- JSON summary: `{summary['outputs']['json']}`",
    ]
    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def finalize_outputs(
    args: argparse.Namespace,
    max_rank: int,
    tickers: list[str],
    all_rows: list[dict],
    failures: list[dict],
    ok_tickers: set[str],
) -> int:
    if not all_rows:
        raise SystemExit("No rows generated")

    trades = pd.DataFrame(all_rows)
    for col in ["entry_ts", "exit_ts"]:
        trades[col] = pd.to_datetime(trades[col], utc=True)
    trades_path = write_trades_frame(trades, OUT_TRADES)

    setup_frames = [aggregate_setups(trades, limit) for limit in (20, max_rank)]
    setup_rows = pd.concat([df for df in setup_frames if not df.empty], ignore_index=True)
    requested = requested_rows(trades, 20) + requested_rows(trades, max_rank)
    mtf_breakdown = mtf_breakdown_rows(trades, 20) + mtf_breakdown_rows(trades, max_rank)
    prob_rows = pd.concat(
        [probability_filter_rows(trades, 20), probability_filter_rows(trades, max_rank)],
        ignore_index=True,
    )

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "indicator": "EWB — Probability Overlay v0",
        "data_provider": args.provider,
        "max_universe_rank": max_rank,
        "tickers_requested": len(tickers),
        "tickers_ok": len(ok_tickers),
        "tickers": tickers,
        "intervals": args.intervals,
        "trade_rows": int(len(trades)),
        "failures": failures,
        "requested_rows": requested,
        "mtf_breakdown": mtf_breakdown,
        "best_balanced": setup_rows.sort_values("balanced_score", ascending=False).head(25).to_dict("records"),
        "best_winrate": setup_rows.sort_values(["winrate", "trades"], ascending=[False, False]).head(25).to_dict("records"),
        "outputs": {
            "markdown": OUT_MD,
            "json": OUT_JSON,
            "trades": trades_path,
        },
    }

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(json_safe(summary), f, ensure_ascii=False, indent=2)
    write_report(summary, trades, setup_rows, prob_rows)
    print(f"Wrote {OUT_MD}")
    print(f"Wrote {OUT_JSON}")
    print(f"Wrote {trades_path}")
    return 0


def main() -> int:
    global TIINGO_DELAY_SECONDS

    parser = argparse.ArgumentParser()
    parser.add_argument("--universe", choices=["top20", "top100"], default="top100")
    parser.add_argument("--intervals", nargs="*", default=list(INTERVALS.keys()))
    parser.add_argument("--provider", choices=["yahoo", "tiingo"], default="yahoo")
    parser.add_argument(
        "--tiingo-delay",
        type=float,
        default=0.0,
        help="Delay in seconds before each Tiingo API request; useful for large top100 runs.",
    )
    parser.add_argument(
        "--reports-only",
        action="store_true",
        help="Build markdown/json/parquet outputs from checkpoint without new data downloads.",
    )
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    TIINGO_DELAY_SECONDS = max(0.0, args.tiingo_delay)

    max_rank = 20 if args.universe == "top20" else 100
    tickers = TOP100_STOCKS[:max_rank]
    calibration = load_probability_calibration(CALIBRATION_PATH)
    checkpoint_path = OUT_TRADES.replace(".parquet", "_checkpoint.parquet")
    all_rows: list[dict] = []
    failures: list[dict] = []
    ok_tickers: set[str] = set()
    processed_pairs: set[tuple[str, str]] = set()

    if args.resume:
        checkpoint = read_checkpoint(checkpoint_path)
        if checkpoint is not None and not checkpoint.empty:
            all_rows.extend(checkpoint.to_dict("records"))
            processed_pairs = set(zip(checkpoint["ticker"], checkpoint["interval"]))
            ok_tickers = set(checkpoint["ticker"].dropna().unique())
            print(f"[resume] loaded {len(checkpoint)} rows, {len(processed_pairs)} pairs")

    if args.reports_only:
        return finalize_outputs(args, max_rank, tickers, all_rows, failures, ok_tickers)

    total = len(tickers) * len(args.intervals)
    done = 0
    for ticker in tickers:
        cache_1h: dict[str, pd.DataFrame | None] = {}
        rank = TOP100_STOCKS.index(ticker) + 1
        for label in args.intervals:
            done += 1
            if (ticker, label) in processed_pairs:
                print(f"[{done:3}/{total}] {ticker:8} {label:3} resume")
                continue
            try:
                df = load_frame(ticker, label, cache_1h, args.provider)
                if df is None or len(df) < 100:
                    failures.append({"ticker": ticker, "interval": label, "error": "not_enough_data"})
                    print(f"[{done:3}/{total}] {ticker:8} {label:3} no data")
                    continue
                rows = build_trades_for_frame(ticker, label, rank, df, calibration)
                all_rows.extend(rows)
                ok_tickers.add(ticker)
                print(f"[{done:3}/{total}] {ticker:8} {label:3} rows={len(rows):5} total={len(all_rows):7}")
                if done % 20 == 0:
                    write_checkpoint(all_rows, checkpoint_path)
            except TiingoRateLimitError as exc:
                write_checkpoint(all_rows, checkpoint_path)
                print(f"[rate-limit] {exc}")
                print(f"[checkpoint] saved {len(all_rows)} rows to {checkpoint_path}")
                return 2
            except Exception as exc:
                failures.append({"ticker": ticker, "interval": label, "error": repr(exc)})
                print(f"[{done:3}/{total}] {ticker:8} {label:3} error={type(exc).__name__}: {exc}")

    return finalize_outputs(args, max_rank, tickers, all_rows, failures, ok_tickers)


if __name__ == "__main__":
    raise SystemExit(main())
