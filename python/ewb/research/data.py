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


def download_ohlc(ticker: str, interval: str, period: str,
                  include_volume: bool = False,
                  min_rows: int = 50) -> pd.DataFrame | None:
    """Download OHLC from yfinance and normalize columns."""
    try:
        df = yf.download(
            ticker,
            period=period,
            interval=interval,
            progress=False,
            auto_adjust=True,
            threads=False,
        )
    except Exception as exc:
        log.warning("download_ohlc failed for %s/%s/%s: %s", ticker, interval, period, exc)
        return None
    return normalize_ohlc(df, include_volume=include_volume, min_rows=min_rows)
