"""Data loading helpers for research scripts."""
from __future__ import annotations

import logging
import pandas as pd
import yfinance as yf

log = logging.getLogger(__name__)

# Shared yfinance session: without it yfinance builds a fresh connection pool per
# download, so a full-watchlist scan that falls through to yfinance (e.g. during
# a Binance/Tiingo outage — every ticker retries here) opens hundreds of sockets
# and can hit "Too many open files" (Errno 24). One reused session caps that.
_YF_SESSION = None
_YF_SESSION_TRIED = False


def _yf_session():
    global _YF_SESSION, _YF_SESSION_TRIED
    if not _YF_SESSION_TRIED:
        _YF_SESSION_TRIED = True
        try:
            from curl_cffi import requests as _cffi
            _YF_SESSION = _cffi.Session(impersonate="chrome")
        except Exception as exc:  # pragma: no cover - optional dep
            log.warning("shared yfinance session unavailable (%s); per-call sessions", exc)
            _YF_SESSION = None
    return _YF_SESSION


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


def _download_yfinance(ticker: str, interval: str, period: str,
                       include_volume: bool, min_rows: int) -> pd.DataFrame | None:
    """Fallback path: yfinance with 4h/2h resampling and 1w->1wk aliasing."""
    iv = str(interval).lower()
    sess = _yf_session()
    yf_kwargs = {"progress": False, "auto_adjust": True, "threads": False}
    if sess is not None:
        yf_kwargs["session"] = sess
    try:
        if iv in _RESAMPLE_FROM:
            base_iv, rule = _RESAMPLE_FROM[iv]
            raw = yf.download(ticker, period=period, interval=base_iv, **yf_kwargs)
            resampled = _resample_ohlc(raw, rule, include_volume)
            return resampled if (resampled is not None and len(resampled) > min_rows) else None
        yf_iv = _INTERVAL_ALIASES.get(iv, iv)
        df = yf.download(ticker, period=period, interval=yf_iv, **yf_kwargs)
    except Exception as exc:
        log.warning("yfinance download failed for %s/%s/%s: %s", ticker, interval, period, exc)
        return None
    return normalize_ohlc(df, include_volume=include_volume, min_rows=min_rows)


def download_ohlc(ticker: str, interval: str, period: str,
                  include_volume: bool = False,
                  min_rows: int = 50) -> pd.DataFrame | None:
    """Download OHLC, routed by asset class.

    Crypto -> Binance (keyless, native 1h/4h/1d/1w). Stocks -> Tiingo (needs
    TIINGO_API_KEY). yfinance is the fallback for both when the primary
    provider returns nothing (or the Tiingo key is absent).
    """
    iv = str(interval).lower()
    try:
        from ewb.research import providers as _prov
        if _prov.is_crypto(ticker):
            df = _prov.download_binance_ohlc(ticker, iv, period, min_rows=min_rows)
        else:
            df = _prov.download_tiingo_ohlc(ticker, iv, period, min_rows=min_rows)
        if df is not None:
            return df
    except Exception as exc:  # pragma: no cover - defensive, keep fallback alive
        log.warning("provider download failed for %s/%s: %s — falling back to yfinance",
                    ticker, interval, exc)
    return _download_yfinance(ticker, interval, period, include_volume, min_rows)
