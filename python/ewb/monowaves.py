"""Monowave detector — ATR-based ZigZag.

Mirrors ZZState.step() from pine/ewb_monowaves_mtf.pine.
A monowave = price movement between two changes of direction (Neely Ch.2).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import numpy as np
import pandas as pd


@dataclass
class Pivot:
    idx: int          # bar index in source series
    price: float
    direction: int    # +1 = high pivot (was up monowave), -1 = low pivot
    # length & duration of the completed monowave that ended here
    price_len: float = 0.0
    time_len: int = 0
    # similarity to previous monowave (AKU-0003)
    similar_to_prev: Optional[bool] = None
    # rule classification of PREVIOUS monowave (m1) — set by classifier
    rule_no: int = 0
    cond_letter: str = ""


@dataclass
class ZZState:
    dir: int = 0                    # 0=uninit, +1=tracking high, -1=tracking low
    pivot_price: float = np.nan
    pivot_bar: int = -1
    ext_price: float = np.nan       # current extremum candidate
    ext_bar: int = -1
    count: int = 0
    last_price_len: float = np.nan
    last_time_len: int = 0
    has_prev: bool = False
    len0: float = np.nan            # m0 (oldest, for rule classifier)
    len1: float = np.nan            # m1 (newest completed)


def _atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int = 14) -> np.ndarray:
    """Wilder ATR (matches Pine ta.atr)."""
    tr = np.maximum(high - low, np.maximum(
        np.abs(high - np.concatenate([[close[0]], close[:-1]])),
        np.abs(low  - np.concatenate([[close[0]], close[:-1]])),
    ))
    atr = np.full_like(tr, np.nan, dtype=float)
    atr[n-1] = tr[:n].mean()
    for i in range(n, len(tr)):
        atr[i] = (atr[i-1] * (n-1) + tr[i]) / n
    return atr


def detect_monowaves(
    df: pd.DataFrame,
    atr_period: int = 14,
    atr_mult: float = 2.5,
    use_atr: bool = True,
    pct_threshold: float = 2.0,
) -> list[Pivot]:
    """Detect monowave pivots on OHLC DataFrame.

    df: must contain columns 'high', 'low', 'close'.
    Returns list of confirmed Pivots (in chronological order).
    """
    if len(df) < atr_period + 2:
        return []

    high  = df["high"].to_numpy(dtype=float)
    low   = df["low"].to_numpy(dtype=float)
    close = df["close"].to_numpy(dtype=float)

    if use_atr:
        atr = _atr(high, low, close, atr_period)
        rev_arr = atr * atr_mult
    else:
        rev_arr = close * pct_threshold / 100.0

    s = ZZState()
    pivots: list[Pivot] = []

    for i in range(len(df)):
        rev = rev_arr[i] if i < len(rev_arr) else np.nan
        if np.isnan(rev):
            continue

        h, l = high[i], low[i]

        if np.isnan(s.ext_price):
            # Init on first valid bar
            s.ext_price = h
            s.ext_bar   = i
            s.pivot_price = l
            s.pivot_bar   = i
            s.dir = 1
            continue

        confirmed = False
        ended_dir = 0

        if s.dir > 0:
            # Tracking high
            if h > s.ext_price:
                s.ext_price = h
                s.ext_bar   = i
            # Reversal down → confirm high pivot
            if l < s.ext_price - rev:
                confirmed = True
                ended_dir = 1
        else:
            # Tracking low
            if l < s.ext_price:
                s.ext_price = l
                s.ext_bar   = i
            if h > s.ext_price + rev:
                confirmed = True
                ended_dir = -1

        if confirmed:
            piv = Pivot(
                idx=s.ext_bar,
                price=s.ext_price,
                direction=ended_dir,
            )
            piv.price_len = abs(s.ext_price - s.pivot_price)
            piv.time_len  = s.ext_bar - s.pivot_bar

            # Similarity AKU-0003 (price OR time ≥ 1/3 of max)
            if s.has_prev:
                pmin = min(piv.price_len, s.last_price_len)
                pmax = max(piv.price_len, s.last_price_len)
                tmin = min(piv.time_len, s.last_time_len)
                tmax = max(piv.time_len, s.last_time_len)
                price_ok = pmax > 0 and pmin >= pmax / 3.0
                time_ok  = tmax > 0 and tmin >= tmax / 3.0
                piv.similar_to_prev = price_ok or time_ok

            pivots.append(piv)
            s.count += 1

            # rotate state
            s.pivot_price = s.ext_price
            s.pivot_bar   = s.ext_bar
            s.dir = -ended_dir
            # start tracking new extremum from CURRENT bar
            if ended_dir == 1:
                s.ext_price = l
                s.ext_bar   = i
            else:
                s.ext_price = h
                s.ext_bar   = i

            # update m0/m1 ladder
            s.len0 = s.len1
            s.len1 = piv.price_len
            s.last_price_len = piv.price_len
            s.last_time_len  = piv.time_len
            s.has_prev = True

    return pivots


def monowave_dirs(pivots: list[Pivot]) -> list[int]:
    """Return list of monowave directions in order. pivots[i].direction is
    the direction of monowave that ENDED at pivots[i]."""
    return [p.direction for p in pivots]
