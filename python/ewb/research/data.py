"""Data loading helpers for research scripts."""
from __future__ import annotations

import logging
import pandas as pd
import yfinance as yf

log = logging.getLogger(__name__)


def normalize_ohlc(df: pd.DataFrame, include_volume: bool = False,
                   min_rows: int = 50) -> pd.DataFrame | None:
    """Normalize yfinance OHLC output to lowercase columns."""
    if df is None or df.empty:
        return None
    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = [c[0] for c in out.columns]
    out.columns = [str(c).lower() for c in out.columns]
    base_cols = ["open", "high", "low", "close"]
    cols = base_cols + (["volume"] if include_volume else [])
    out = out[[c for c in cols if c in out.columns]].dropna()
    return out if len(out) > min_rows else None


# yfinance has no native "4h" or "1w" interval. Map aliases to supported
# intervals; build 4h bars by resampling 1h data so the scanner produces real
# signals on 1h / 4h / 1d / 1w.
_INTERVAL_ALIASES = {"1w": "1wk", "1week": "1wk", "1wk": "1wk"}
_RESAMPLE_FROM = {"4h": ("1h", "4h"), "2h": ("1h", "2h")}


def _resample_ohlc(df: pd.DataFrame, rule: str, include_volume: bool) -> pd.DataFrame | None:
    if df is None or df.empty:
        return None
    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = [c[0] for c in out.columns]
    out.columns = [str(c).lower() for c in out.columns]
    agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
    if include_volume and "volume" in out.columns:
        agg["volume"] = "sum"
    cols = [c for c in agg if c in out.columns]
    if not {"open", "high", "low", "close"}.issubset(cols):
        return None
    return out[cols].resample(rule).agg(agg).dropna()


def download_ohlc(ticker: str, interval: str, period: str,
                  include_volume: bool = False,
                  min_rows: int = 50) -> pd.DataFrame | None:
    """Download OHLC from yfinance and normalize columns.

    Supports "4h"/"2h" (resampled from 1h) and "1w" (alias of 1wk) on top of
    yfinance's native intervals.
    """
    iv = str(interval).lower()
    try:
        if iv in _RESAMPLE_FROM:
            base_iv, rule = _RESAMPLE_FROM[iv]
            raw = yf.download(ticker, period=period, interval=base_iv,
                              progress=False, auto_adjust=True, threads=False)
            resampled = _resample_ohlc(raw, rule, include_volume)
            return resampled if (resampled is not None and len(resampled) > min_rows) else None
        yf_iv = _INTERVAL_ALIASES.get(iv, iv)
        df = yf.download(ticker, period=period, interval=yf_iv,
                         progress=False, auto_adjust=True, threads=False)
    except Exception as exc:
        log.warning("download_ohlc failed for %s/%s/%s: %s", ticker, interval, period, exc)
        return None
    return normalize_ohlc(df, include_volume=include_volume, min_rows=min_rows)
