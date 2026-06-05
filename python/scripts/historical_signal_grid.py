"""Historical signal grid for Elliott Wave Brain.

This script is intentionally research-only. It uses the current Python
monowave/figure/HTF code as the source of truth and writes a report that can
be used before changing Pine defaults.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
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

from ewb.figures import match_figures
from ewb.htf import htf_bias_series, resample_ohlc
from ewb.monowaves import detect_monowaves
from ewb.research import cost_for, download_ohlc
from ewb.research.universe import CRYPTO
from ewb.research.probability import (
    load_probability_calibration,
    lookup_probability_row,
)
from ewb.rules import classify_pivots


REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CALIBRATION_PATH = os.path.join(
    REPO, "brain-output", "indicator-spec", "probability_calibration_v0.json"
)
CRYPTO_CALIBRATION_PATH = os.path.join(
    REPO, "brain-output", "indicator-spec", "probability_calibration_crypto_v0.json"
)
OUT_MD = os.path.join(REPO, "docs", "validation", "historical_signal_grid_report.md")
OUT_JSON = os.path.join(
    REPO, "brain-output", "signals", "historical_signal_grid_summary.json"
)
OUT_TRADES = os.path.join(REPO, "python", "data", "historical_signal_grid_trades.parquet")
ACTIVE_ASSET_CLASS = "stocks"
ACTIVE_UNIVERSE: list[str] = []


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

CRYPTO_UNIVERSE = CRYPTO


INTERVALS = {
    "15m": {"yf": "15m", "period": "60d", "htf": "1h", "source": "direct"},
    "30m": {"yf": "30m", "period": "60d", "htf": "1h", "source": "direct"},
    "1h": {"yf": "1h", "period": "730d", "htf": "4h", "source": "direct"},
    "4h": {"yf": "1h", "period": "730d", "htf": "1D", "source": "resample_4h"},
    "1d": {"yf": "1d", "period": "5y", "htf": "1W", "source": "direct"},
    "1w": {"yf": "1wk", "period": "10y", "htf": "1ME", "source": "direct"},
}

BINANCE_INTERVAL_MS = {
    "15m": 15 * 60 * 1000,
    "30m": 30 * 60 * 1000,
    "1h": 60 * 60 * 1000,
    "4h": 4 * 60 * 60 * 1000,
    "1d": 24 * 60 * 60 * 1000,
    "1w": 7 * 24 * 60 * 60 * 1000,
}

CRYPTO_HISTORY_DAYS = {
    "15m": 180,
    "30m": 365,
    "1h": 730,
    "4h": 1460,
    "1d": 1825,
    "1w": 3650,
}

TRADE_PATTERNS = {"flat", "double_corr"}
RESEARCH_PATTERNS = {"impulse", "triangle"}
EXIT_BARS = {"flat": 20, "double_corr": 50, "impulse": 50, "triangle": 30}
ENTRY_VARIANTS = ("confirm_close", "next_open")
TP_MULTS = (0.5, 0.618, 1.0, 1.618)
SL_MULTS = (0.75, 1.0, 1.25)
LATE_LIMITS = (0.20, 0.35, 0.50, 999.0)
MTF_POLICIES = (
    "none",
    "warn",
    "block_against_htf",
    "long_only_htf_up_short_only_htf_down",
    "fade_not_against_htf",
)
PROB_THRESHOLDS = (50, 52, 55, 58, 60, 65)
SAMPLE_THRESHOLDS = (0, 30, 50, 100)


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


def side_from_direction(fig_type: str, direction: str) -> tuple[str, str]:
    """Return (mode, side) for the test contract."""
    if fig_type in TRADE_PATTERNS:
        return "fade", "short" if direction == "up" else "long"
    if fig_type == "impulse":
        return "follow_research", "long" if direction == "up" else "short"
    return "context_research", "short" if direction == "up" else "long"


def side_int(side: str) -> int:
    return 1 if side == "long" else -1


def clean_timestamp(ts) -> str:
    return pd.Timestamp(ts).isoformat()


def output_paths(asset_class: str) -> tuple[str, str, str]:
    if asset_class == "crypto":
        return (
            os.path.join(REPO, "docs", "validation", "historical_signal_grid_crypto_report.md"),
            os.path.join(REPO, "brain-output", "signals", "historical_signal_grid_crypto_summary.json"),
            os.path.join(REPO, "python", "data", "historical_signal_grid_crypto_trades.parquet"),
        )
    return (
        os.path.join(REPO, "docs", "validation", "historical_signal_grid_report.md"),
        os.path.join(REPO, "brain-output", "signals", "historical_signal_grid_summary.json"),
        os.path.join(REPO, "python", "data", "historical_signal_grid_trades.parquet"),
    )


def checkpoint_path_for(trades_path: str) -> str:
    return trades_path.replace(".parquet", "_checkpoint.parquet")


def write_trades_frame(df: pd.DataFrame, path: str) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        df.to_parquet(path, index=False)
        return path
    except Exception:
        csv_path = path.replace(".parquet", ".csv")
        df.to_csv(csv_path, index=False)
        return csv_path


def calibration_for_asset_class(asset_class: str) -> tuple[str, dict]:
    if asset_class == "crypto":
        if os.path.exists(CRYPTO_CALIBRATION_PATH):
            return CRYPTO_CALIBRATION_PATH, load_probability_calibration(CRYPTO_CALIBRATION_PATH)
        return CRYPTO_CALIBRATION_PATH, {
            "asset_class": "crypto",
            "model_version": "probability-calibration-crypto-v0-missing",
            "lookup_priority": [],
            "rows": [],
        }
    return CALIBRATION_PATH, load_probability_calibration(CALIBRATION_PATH)


def universe_rank_for(ticker: str) -> int:
    universe = ACTIVE_UNIVERSE or TOP100_STOCKS
    return universe.index(ticker) + 1 if ticker in universe else 999


def binance_symbol_for(ticker: str) -> str:
    """Map yfinance-style crypto tickers to Binance USDT symbols."""
    base = ticker.replace("-USD", "").replace("-USDT", "")
    return f"{base}USDT"


def download_binance_ohlc(
    ticker: str,
    interval: str,
    days: int | None = None,
    limit: int = 1000,
    max_requests: int = 80,
) -> pd.DataFrame | None:
    """Download crypto OHLCV from Binance public klines without extra deps."""
    symbol = binance_symbol_for(ticker)
    interval_ms = BINANCE_INTERVAL_MS.get(interval)
    if interval_ms is None:
        return None

    end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    if days is None:
        start_ms = end_ms - interval_ms * limit
    else:
        start_ms = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)

    payload: list = []
    requests = 0
    while start_ms < end_ms and requests < max_requests:
        params = urllib.parse.urlencode({
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
            "startTime": start_ms,
            "endTime": end_ms,
        })
        url = f"https://api.binance.com/api/v3/klines?{params}"
        try:
            with urllib.request.urlopen(url, timeout=20) as response:
                chunk = json.load(response)
        except Exception:
            return None if not payload else _binance_payload_to_ohlc(payload)
        if not isinstance(chunk, list) or not chunk:
            break
        payload.extend(chunk)
        requests += 1
        last_open_ms = int(chunk[-1][0])
        next_start = last_open_ms + interval_ms
        if next_start <= start_ms:
            break
        start_ms = next_start
        if len(chunk) < limit:
            break
        time.sleep(0.05)

    return _binance_payload_to_ohlc(payload)


def _binance_payload_to_ohlc(payload: list) -> pd.DataFrame | None:
    if not payload:
        return None
    rows = []
    for row in payload:
        rows.append({
            "ts": pd.to_datetime(int(row[0]), unit="ms", utc=True),
            "open": float(row[1]),
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
            "volume": float(row[5]),
        })
    df = pd.DataFrame(rows).drop_duplicates("ts").set_index("ts").sort_index()
    return df if len(df) >= 50 else None


def load_frame(ticker: str, label: str, cache_1h: dict[str, pd.DataFrame | None]) -> pd.DataFrame | None:
    if ACTIVE_ASSET_CLASS == "crypto":
        interval = "1w" if label == "1w" else label
        return download_binance_ohlc(ticker, interval, days=CRYPTO_HISTORY_DAYS.get(label))
    cfg = INTERVALS[label]
    if cfg["source"] == "resample_4h":
        raw = cache_1h.get(ticker)
        if raw is None:
            raw = download_ohlc(ticker, "1h", "730d", min_rows=100)
            cache_1h[ticker] = raw
        return resample_ohlc(raw, "4h") if raw is not None else None
    df = download_ohlc(ticker, cfg["yf"], cfg["period"], min_rows=100)
    if label == "1h":
        cache_1h[ticker] = df
    return df


def entry_variants(df: pd.DataFrame, confirm_idx: int, side: str, amp: float) -> list[Entry]:
    out: list[Entry] = []
    if confirm_idx < 0 or confirm_idx >= len(df):
        return out
    close = df["close"].to_numpy(float)
    open_ = df["open"].to_numpy(float)
    confirm_px = float(close[confirm_idx])
    if confirm_px > 0:
        out.append(Entry(
            "confirm_close",
            confirm_idx,
            confirm_px,
            df.index[confirm_idx],
            0.0,
        ))
    next_idx = confirm_idx + 1
    if next_idx < len(df) and open_[next_idx] > 0 and amp > 0:
        sign = side_int(side)
        progress = sign * (float(open_[next_idx]) - confirm_px) / amp
        next_variant = "next_bar_open" if ACTIVE_ASSET_CLASS == "crypto" else "next_open"
        out.append(Entry(
            next_variant,
            next_idx,
            float(open_[next_idx]),
            df.index[next_idx],
            progress,
        ))
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
    n = len(df)
    if amp <= 0 or entry.idx + 1 >= n:
        return None
    tp = entry.px + sign * amp * tp_mult
    sl = entry.px - sign * amp * sl_mult
    last_idx = min(entry.idx + exit_bars, n - 1)
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


def mtf_allowed(policy: str, side: str, bias: int, direction: str) -> bool:
    if policy in {"none", "warn"}:
        return True
    if policy in {"block_against_htf", "fade_not_against_htf"}:
        if side == "long":
            return bias >= 0
        return bias <= 0
    if policy == "long_only_htf_up_short_only_htf_down":
        if side == "long":
            return bias > 0
        return bias < 0
    return True


def probability_meta(calibration: dict, fig_type: str, interval: str, side: str) -> dict:
    row = lookup_probability_row(calibration, fig_type, interval, side)
    if row is None:
        return {
            "p_win_model": np.nan,
            "sample_size": 0,
            "confidence": "unknown",
            "model_ev": np.nan,
            "lookup_key": "",
            "lookup_level": "",
        }
    return {
        "p_win_model": float(row.get("p_trade_win") or np.nan) * 100,
        "sample_size": int(row.get("n") or 0),
        "confidence": row.get("confidence", "unknown"),
        "model_ev": float(row.get("expected_net_return") or np.nan),
        "lookup_key": row.get("key", ""),
        "lookup_level": row.get("level", ""),
    }


def build_trades_for_frame(
    ticker: str,
    label: str,
    df: pd.DataFrame,
    calibration: dict,
) -> list[dict]:
    pivots = detect_monowaves(df, atr_mult=2.5)
    classify_pivots(pivots)
    figures = match_figures(pivots)
    bias_series = htf_bias_series(df, INTERVALS[label]["htf"])
    cost = cost_for(ticker)
    rows: list[dict] = []
    for fig in figures:
        if not fig.confirmed:
            continue
        if fig.type not in TRADE_PATTERNS | RESEARCH_PATTERNS:
            continue
        if not fig.pivots:
            continue
        confirm_idx = fig.pivots[-1].confirmation_idx
        if confirm_idx < 0:
            continue
        mode, side = side_from_direction(fig.type, fig.direction)
        if fig.amplitude <= 0:
            continue
        entries = entry_variants(df, confirm_idx, side, fig.amplitude)
        if not entries:
            continue
        pmeta = probability_meta(calibration, fig.type, label, side)
        htf_bias = int(bias_series.iloc[confirm_idx]) if confirm_idx < len(bias_series) else 0
        policies = MTF_POLICIES if fig.type in TRADE_PATTERNS else ("none",)
        if fig.type in RESEARCH_PATTERNS:
            entries = [entry for entry in entries if entry.variant == "confirm_close"]
        for policy in policies:
            if not mtf_allowed(policy, side, htf_bias, fig.direction):
                continue
            for entry in entries:
                if entry.idx + 2 >= len(df):
                    continue
                late_limits = LATE_LIMITS if entry.variant == "next_open" else (999.0,)
                for late_limit in late_limits:
                    if entry.progress_to_tp > late_limit:
                        continue
                    tp_values = TP_MULTS if fig.type in TRADE_PATTERNS else (1.0,)
                    sl_values = SL_MULTS if fig.type in TRADE_PATTERNS else (1.0,)
                    for tp_mult in tp_values:
                        for sl_mult in sl_values:
                            result = simulate_full_exit(
                                df,
                                entry,
                                side,
                                float(fig.amplitude),
                                EXIT_BARS[fig.type],
                                tp_mult,
                                sl_mult,
                                cost,
                            )
                            if result is None:
                                continue
                            rows.append({
                                **base_record(
                                    ticker, label, fig, side, mode, policy, entry,
                                    late_limit, tp_mult, sl_mult, "full", htf_bias, pmeta
                                ),
                                **result,
                            })
                    if fig.type not in TRADE_PATTERNS:
                        continue
                    for sl_mult in SL_MULTS:
                        result = simulate_partial_exit(
                            df,
                            entry,
                            side,
                            float(fig.amplitude),
                            EXIT_BARS[fig.type],
                            sl_mult,
                            cost,
                        )
                        if result is None:
                            continue
                        rows.append({
                            **base_record(
                                ticker, label, fig, side, mode, policy, entry,
                                late_limit, 1.618, sl_mult, "partial_50_100_1618",
                                htf_bias, pmeta
                            ),
                            **result,
                        })
    return rows


def base_record(
    ticker: str,
    label: str,
    fig,
    side: str,
    mode: str,
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
        "ticker": ticker,
        "asset_class": ACTIVE_ASSET_CLASS,
        "universe_rank": universe_rank_for(ticker),
        "interval": label,
        "fig_type": fig.type,
        "mode": mode,
        "direction": fig.direction,
        "side": side,
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
        "amp_pct": float(fig.amplitude / entry.px),
        "pattern_start_idx": int(fig.start_idx),
        "pattern_end_idx": int(fig.end_idx),
        "confirm_idx": int(fig.pivots[-1].confirmation_idx),
        "confirmation_lag": int(fig.pivots[-1].confirmation_idx - fig.end_idx),
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
        return {"folds": [], "positive_ev_folds": 0, "winrate_std": np.nan}
    return {
        "folds": rows,
        "positive_ev_folds": int(sum(1 for r in rows if r.get("ev", 0) > 0)),
        "winrate_std": float(np.std([r["winrate"] for r in rows], ddof=0)),
        "ev_std": float(np.std([r["ev"] for r in rows], ddof=0)),
    }


def confidence_label(row: dict) -> str:
    n = row.get("trades", 0)
    pf = row.get("profit_factor", np.nan)
    dd = abs(row.get("max_drawdown", 0) or 0)
    pos_folds = row.get("positive_ev_folds", 0)
    if n >= 50 and pf >= 1.5 and dd <= 0.20 and pos_folds >= 4:
        return "high"
    if n >= 30 and pf >= 1.2 and dd <= 0.30 and pos_folds >= 3:
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


def aggregate_setups(trades: pd.DataFrame, universe_limit: int) -> tuple[pd.DataFrame, list[dict]]:
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
        wf = (
            walk_forward_metrics(grp)
            if len(grp) >= 30
            else {"positive_ev_folds": 0, "winrate_std": np.nan, "ev_std": np.nan}
        )
        row = dict(zip(groups, key))
        row.update(m)
        row.update({
            "universe": f"top{universe_limit}",
            "p_win_model": float(grp["p_win_model"].dropna().iloc[0]) if not grp["p_win_model"].dropna().empty else np.nan,
            "sample_size": int(grp["sample_size"].max()) if "sample_size" in grp else 0,
            "model_confidence": str(grp["confidence"].dropna().iloc[0]) if not grp["confidence"].dropna().empty else "unknown",
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

    setup_df = pd.DataFrame(rows)
    if setup_df.empty:
        return setup_df, []

    filtered_rows = []
    for min_p in PROB_THRESHOLDS:
        for min_n in SAMPLE_THRESHOLDS:
            for exclude_low in (False, True):
                filt = setup_df[
                    (setup_df["p_win_model"] >= min_p)
                    & (setup_df["sample_size"] >= min_n)
                ].copy()
                if exclude_low:
                    filt = filt[filt["model_confidence"] != "low"]
                if filt.empty:
                    continue
                filt["min_p_win"] = min_p
                filt["min_sample"] = min_n
                filt["exclude_low_confidence"] = exclude_low
                filtered_rows.extend(filt.to_dict("records"))
    return setup_df, filtered_rows


def table(rows: Iterable[dict], columns: list[tuple[str, str]], limit: int = 12) -> list[str]:
    rows = list(rows)[:limit]
    header = "| " + " | ".join(title for title, _ in columns) + " |"
    sep = "|" + "|".join("---" for _ in columns) + "|"
    lines = [header, sep]
    for row in rows:
        vals = []
        for _, key in columns:
            value = row.get(key)
            if key in {"winrate", "ev", "median_return", "max_drawdown", "tp_rate", "sl_rate", "time_rate", "test_winrate", "test_ev"}:
                vals.append(pct(value, 2 if key in {"ev", "median_return", "test_ev"} else 1))
            elif key in {"profit_factor", "avg_holding_bars", "balanced_score"}:
                vals.append(num(value, 2))
            elif key == "late_limit":
                vals.append("off" if float(value) > 10 else f"{float(value) * 100:.0f}%")
            elif key in {"tp_mult", "sl_mult"}:
                vals.append(num(value, 3))
            else:
                vals.append(str(value))
        lines.append("| " + " | ".join(vals) + " |")
    return lines


def write_report(summary: dict, setup_rows: pd.DataFrame, probability_rows: list[dict]) -> None:
    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    trade_setups = setup_rows[setup_rows["fig_type"].isin(TRADE_PATTERNS)].copy()
    research_setups = setup_rows[setup_rows["fig_type"].isin(RESEARCH_PATTERNS)].copy()
    best_win = setup_rows[
        setup_rows["fig_type"].isin(TRADE_PATTERNS)
        & (setup_rows["trades"] >= 30)
        & (setup_rows["ev"] > 0)
        & (setup_rows["test_ev"] > 0)
    ].sort_values(["winrate", "trades"], ascending=[False, False]).head(15)
    conf_rank = {"high": 3, "medium": 2, "low": 1}
    best_bal = trade_setups[
        (trade_setups["trades"] >= 50)
        & (trade_setups["ev"] > 0)
        & (trade_setups["validation_ev"] > 0)
        & (trade_setups["test_ev"] > 0)
        & (trade_setups["max_drawdown"] >= -0.35)
        & (trade_setups["profit_factor"] >= 1.2)
        & (trade_setups["positive_ev_folds"] >= 3)
    ].assign(
        conf_rank=lambda df: df["confidence"].map(conf_rank).fillna(0)
    ).sort_values(["conf_rank", "balanced_score"], ascending=False).head(15)
    bad = trade_setups[
        (trade_setups["trades"] >= 30)
        & ((trade_setups["ev"] <= 0) | (trade_setups["test_ev"] <= 0))
    ].sort_values(["ev", "test_ev"]).head(15)
    research = research_setups[
        research_setups["trades"] >= 30
    ].sort_values("balanced_score", ascending=False).head(15)

    columns = [
        ("Universe", "universe"), ("TF", "interval"), ("Pattern", "fig_type"),
        ("Side", "side"), ("MTF", "mtf_policy"), ("Entry", "entry_variant"),
        ("Late", "late_limit"), ("TP", "tp_mult"), ("SL", "sl_mult"),
        ("Exit", "exit_plan"), ("Trades", "trades"), ("Win", "winrate"),
        ("EV", "ev"), ("Test win", "test_winrate"), ("Test EV", "test_ev"),
        ("DD", "max_drawdown"), ("PF", "profit_factor"), ("Conf", "confidence"),
    ]

    scope_line = (
        "Scope: crypto only. Stocks, ETFs, FX and futures are excluded. Entry is evaluated on the figure confirmation bar or later; `next_bar_open` means the next 24/7 crypto bar open."
        if summary.get("asset_class") == "crypto"
        else "Scope: stocks only. Crypto, FX, futures and ETFs are excluded. Entry is evaluated on the figure confirmation bar or later, never on the historical extremum bar."
    )
    calibration_line = (
        f"- Calibration source: `{summary.get('calibration_path')}`. If the crypto calibration file is missing, probability filters are disabled and the run is treated as uncalibrated research."
        if summary.get("asset_class") == "crypto"
        else "- Keep the probability model as baseline `probability_calibration_v0.json`; do not mix it with top20/watchlist calibration inside Pine."
    )
    default_lines = (
        [
            "- Crypto is research-only until `probability_calibration_crypto_v0.json` exists and passes Pine/Python parity.",
            "- Main candidate patterns remain `flat` and `double_corr` fade only; do not reuse stock P(win) on crypto.",
            "- Prefer `next_bar_open`/fresh signal behavior for practical alerts, but do not display stale entries after TP progress exceeds the selected late-entry limit.",
            "- Treat missing calibration, low sample size, or low confidence as WAIT/research.",
        ]
        if summary.get("asset_class") == "crypto"
        else [
            "- Main trade patterns: `flat` and `double_corr` fade only.",
            "- Keep `impulse` and `triangle` as WAIT/research context unless a future out-of-sample run proves stable positive EV.",
            "- Prefer `next_open`/fresh signal behavior for practical alerts, but do not display stale entries after TP progress exceeds the selected late-entry limit.",
            "- Treat rows with low sample size as B/C or WAIT even when raw winrate is high.",
        ]
    )
    risk_lines = (
        [
            "- Crypto MVP uses Binance public klines; exchange-grade validation should still compare venues before Pine production defaults.",
            "- Crypto trades 24/7; daily/weekly bar boundaries can differ by data source/timezone.",
            "- Spot/perpetual futures must not share one calibration because funding, leverage and liquidation risk change EV.",
            "- Same-bar TP/SL ambiguity is resolved conservatively by checking SL before TP.",
        ]
        if summary.get("asset_class") == "crypto"
        else [
            "- Intraday yfinance history is limited, so 15m/30m OOS sample is smaller than daily/weekly.",
            "- This is a parameter grid; final Pine defaults should use balanced/OOS rows, not max in-sample winrate.",
            "- HTF bias uses confirmed HTF pivots through `confirmation_idx`; if Pine diverges, Python remains source of truth.",
            "- Same-bar TP/SL ambiguity is resolved conservatively by checking SL before TP.",
        ]
    )

    lines = [
        "# Historical Signal Grid - Elliott Wave Brain",
        "",
        f"Generated: `{summary['generated_at']}`",
        "",
        scope_line,
        "",
        "## Run scope",
        "",
        f"- Asset class: `{summary.get('asset_class', 'stocks')}`.",
        f"- Requested universe modes: top20/top50/top100; executed max rank: `{summary['max_universe_rank']}`.",
        f"- Tickers with usable data: `{summary['tickers_ok']}` / `{summary['tickers_requested']}`.",
        f"- Base simulated rows after variants: `{summary['trade_rows']}`.",
        f"- Timeframes: `{', '.join(summary['intervals'])}`.",
        calibration_line,
        "",
        "## Best winrate setups",
        "",
        *table(best_win.to_dict("records"), columns),
        "",
        "## Best balanced setups",
        "",
        *table(best_bal.to_dict("records"), columns),
        "",
        "## Setups to disable or keep as WAIT/research",
        "",
        *table(bad.to_dict("records"), columns),
        "",
        "## Research only: impulse/triangle check",
        "",
        *table(research.to_dict("records"), columns),
        "",
        "## Probability filter observations",
        "",
    ]
    if probability_rows:
        prob_df = pd.DataFrame(probability_rows)
        prob_best = prob_df[
            prob_df["fig_type"].isin(TRADE_PATTERNS)
            & (prob_df["trades"] >= 20)
            & (prob_df["ev"] > 0)
            & (prob_df["test_ev"] > 0)
        ].sort_values("balanced_score", ascending=False).head(10)
        prob_cols = columns + [
            ("Min P", "min_p_win"), ("Min N", "min_sample"),
            ("No low", "exclude_low_confidence"),
        ]
        lines.extend(table(prob_best.to_dict("records"), prob_cols, limit=10))
    else:
        lines.append("No probability-filtered rows passed minimum sample constraints.")

    lines.extend([
        "",
        "## Recommended indicator defaults",
        "",
        *default_lines,
        "",
        "## Risks",
        "",
        *risk_lines,
        "",
        "## Files",
        "",
        f"- Trades: `{OUT_TRADES}`",
        f"- JSON summary: `{OUT_JSON}`",
    ])
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset-class", choices=["stocks", "crypto"], default="stocks")
    parser.add_argument("--universe", choices=["top20", "top50", "top100"], default="top50")
    parser.add_argument("--intervals", nargs="*", default=list(INTERVALS.keys()))
    parser.add_argument(
        "--from-trades",
        action="store_true",
        help="Reuse python/data/historical_signal_grid_trades.parquet and rebuild reports only.",
    )
    parser.add_argument(
        "--resume-checkpoint",
        action="store_true",
        help="Resume from *_checkpoint.parquet when a long grid run was interrupted.",
    )
    args = parser.parse_args()

    global ACTIVE_ASSET_CLASS, ACTIVE_UNIVERSE, OUT_MD, OUT_JSON, OUT_TRADES
    ACTIVE_ASSET_CLASS = args.asset_class
    ACTIVE_UNIVERSE = CRYPTO_UNIVERSE if args.asset_class == "crypto" else TOP100_STOCKS
    OUT_MD, OUT_JSON, OUT_TRADES = output_paths(args.asset_class)

    max_rank = int(args.universe.replace("top", ""))
    max_rank = min(max_rank, len(ACTIVE_UNIVERSE))
    tickers = ACTIVE_UNIVERSE[:max_rank]
    ok_tickers = set()
    failures: list[dict] = []
    checkpoint_path = checkpoint_path_for(OUT_TRADES)

    if args.from_trades:
        trades = pd.read_parquet(OUT_TRADES)
        trades = trades[trades["universe_rank"] <= max_rank].copy()
        ok_tickers = set(trades["ticker"].dropna().unique())
    else:
        calibration_path, calibration = calibration_for_asset_class(args.asset_class)
        all_rows: list[dict] = []
        processed_pairs: set[tuple[str, str]] = set()
        if args.resume_checkpoint and os.path.exists(checkpoint_path):
            checkpoint = pd.read_parquet(checkpoint_path)
            all_rows = checkpoint.to_dict("records")
            processed_pairs = set(zip(checkpoint["ticker"], checkpoint["interval"]))
            ok_tickers = set(checkpoint["ticker"].dropna().unique())
            print(
                f"Resuming checkpoint: {checkpoint_path} "
                f"rows={len(all_rows)} pairs={len(processed_pairs)}",
                flush=True,
            )
        cache_1h: dict[str, pd.DataFrame | None] = {}
        start = time.time()
        total = len(tickers) * len(args.intervals)
        done = 0
        for ticker in tickers:
            for label in args.intervals:
                done += 1
                if (ticker, label) in processed_pairs:
                    print(f"[{done:03}/{total}] {ticker:6} {label:3} skipped checkpoint", flush=True)
                    continue
                try:
                    df = load_frame(ticker, label, cache_1h)
                    if df is None or len(df) < 100:
                        failures.append({"ticker": ticker, "interval": label, "error": "not_enough_data"})
                        continue
                    rows = build_trades_for_frame(ticker, label, df, calibration)
                    all_rows.extend(rows)
                    ok_tickers.add(ticker)
                    elapsed = time.time() - start
                    eta = elapsed / max(done, 1) * (total - done)
                    print(
                        f"[{done:03}/{total}] {ticker:6} {label:3} rows={len(rows):5} "
                        f"total={len(all_rows):7} elapsed={elapsed:.0f}s eta={eta:.0f}s",
                        flush=True,
                    )
                    write_trades_frame(pd.DataFrame(all_rows), checkpoint_path)
                except Exception as exc:
                    failures.append({"ticker": ticker, "interval": label, "error": repr(exc)})
                    print(f"[{done:03}/{total}] {ticker:6} {label:3} ERROR {exc!r}", flush=True)

        if not all_rows:
            raise SystemExit("No trades generated.")

        trades = pd.DataFrame(all_rows)
        write_trades_frame(trades, OUT_TRADES)
        if os.path.exists(checkpoint_path):
            os.remove(checkpoint_path)

    trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
    trades["exit_ts"] = pd.to_datetime(trades["exit_ts"], utc=True)

    setup_frames = []
    probability_rows: list[dict] = []
    for limit in (20, 50, 100):
        if limit > max_rank:
            continue
        setup_df, prob_rows = aggregate_setups(trades, limit)
        setup_frames.append(setup_df)
        probability_rows.extend(prob_rows)
    setup_rows = pd.concat(setup_frames, ignore_index=True)
    trade_setup_rows = setup_rows[setup_rows["fig_type"].isin(TRADE_PATTERNS)].copy()
    summary_conf_rank = {"high": 3, "medium": 2, "low": 1}

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "asset_class": args.asset_class,
        "calibration_path": calibration_path if not args.from_trades else (
            CRYPTO_CALIBRATION_PATH if args.asset_class == "crypto" else CALIBRATION_PATH
        ),
        "max_universe_rank": max_rank,
        "tickers_requested": len(tickers),
        "tickers_ok": len(ok_tickers),
        "tickers": tickers,
        "intervals": args.intervals,
        "trade_rows": int(len(trades)),
        "setup_rows": int(len(setup_rows)),
        "probability_filter_rows": int(len(probability_rows)),
        "failures": failures[:100],
        "outputs": {"markdown": OUT_MD, "json": OUT_JSON, "trades": OUT_TRADES},
        "best_balanced": trade_setup_rows[
            (trade_setup_rows["trades"] >= 50)
            & (trade_setup_rows["ev"] > 0)
            & (trade_setup_rows["validation_ev"] > 0)
            & (trade_setup_rows["test_ev"] > 0)
            & (trade_setup_rows["max_drawdown"] >= -0.35)
            & (trade_setup_rows["profit_factor"] >= 1.2)
            & (trade_setup_rows["positive_ev_folds"] >= 3)
        ].assign(
            conf_rank=lambda df: df["confidence"].map(summary_conf_rank).fillna(0)
        ).sort_values(["conf_rank", "balanced_score"], ascending=False).head(25).to_dict("records"),
        "best_winrate": trade_setup_rows[
            (trade_setup_rows["trades"] >= 30)
            & (trade_setup_rows["ev"] > 0)
            & (trade_setup_rows["test_ev"] > 0)
        ].sort_values(["winrate", "trades"], ascending=[False, False]).head(25).to_dict("records"),
    }
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)
    write_report(summary, setup_rows, probability_rows)
    print(f"Report: {OUT_MD}")
    print(f"Summary: {OUT_JSON}")
    print(f"Trades: {OUT_TRADES}")


if __name__ == "__main__":
    main()
