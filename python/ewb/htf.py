"""HTF bias detector — last-2-monowaves direction.

Returns bias in {-2, -1, 0, +1, +2} where:
+2 strong bull (2 last HTF monowaves both up)
+1 weak bull (last up, prev down or unknown)
 0 flat (alternating or insufficient data)
-1 weak bear
-2 strong bear
"""
from __future__ import annotations
import pandas as pd
from .monowaves import detect_monowaves, Pivot


def htf_bias_from_pivots(pivots: list[Pivot]) -> int:
    """Compute bias from last 2 confirmed pivots' directions."""
    if len(pivots) == 0:
        return 0
    last = pivots[-1].direction
    if len(pivots) == 1:
        return last
    prev = pivots[-2].direction
    if last == prev:
        return 2 * last     # strong: both same direction
    return last             # weak: alternating, but last wave defines tilt


def _structural_trend(pivots: list[Pivot]) -> int:
    """Trend from the HTF pivot LADDER (higher-highs+higher-lows = up).

    The last-pivot-direction approach degenerates because monowave pivots strictly
    alternate (so |bias|=2 is unreachable and the sign just tracks the latest
    swing). Dow/Neely structural trend instead compares successive highs and lows:

      +2 strong up   : last 3 highs and 3 lows each strictly ascending
      +1 weak up     : last 2 highs and 2 lows ascending
       0 sideways    : highs/lows disagree or too few pivots
      -1 weak down   : last 2 highs and 2 lows descending
      -2 strong down : last 3 highs and 3 lows each strictly descending

    Highs are pivots that cap an up-move (direction>0), lows cap a down-move
    (direction<0).
    """
    highs = [p.price for p in pivots if p.direction > 0]
    lows = [p.price for p in pivots if p.direction < 0]
    if len(highs) < 2 or len(lows) < 2:
        return 0

    def _mono(xs: list[float], n: int, ascending: bool) -> bool:
        seg = xs[-n:]
        if len(seg) < n:
            return False
        return all((seg[i] < seg[i + 1]) if ascending else (seg[i] > seg[i + 1])
                   for i in range(len(seg) - 1))

    up2 = _mono(highs, 2, True) and _mono(lows, 2, True)
    down2 = _mono(highs, 2, False) and _mono(lows, 2, False)
    if up2:
        strong = _mono(highs, 3, True) and _mono(lows, 3, True)
        return 2 if strong else 1
    if down2:
        strong = _mono(highs, 3, False) and _mono(lows, 3, False)
        return -2 if strong else -1
    return 0


def structural_trend_series(df: pd.DataFrame, htf_rule: str,
                            atr_period: int = 14, atr_mult: float = 1.5) -> pd.Series:
    """Structural HTF trend at each CTF bar (no look-ahead).

    Like htf_bias_series but uses the pivot-ladder trend (_structural_trend) and a
    finer atr_mult so the higher degree actually carries information. Pivots become
    known at their CONFIRMATION bar, never the extremum bar.
    """
    htf_df = resample_ohlc(df, htf_rule)
    htf_pivots = detect_monowaves(htf_df, atr_period=atr_period, atr_mult=atr_mult)
    out = pd.Series(0, index=df.index, dtype=int)
    if not htf_pivots:
        return out
    pivot_ts = [htf_df.index[p.confirmation_idx if p.confirmation_idx >= 0 else p.idx]
                for p in htf_pivots]
    p_iter = 0
    current = 0
    confirmed: list[Pivot] = []
    for ts in df.index:
        while p_iter < len(htf_pivots) and pivot_ts[p_iter] <= ts:
            confirmed.append(htf_pivots[p_iter])
            current = _structural_trend(confirmed)
            p_iter += 1
        out.loc[ts] = current
    return out


def resample_ohlc(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Resample CTF OHLC to HTF using pandas. rule e.g. '1D','4H','1W'."""
    agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
    if "volume" in df.columns:
        agg["volume"] = "sum"
    out = df.resample(rule).agg(agg).dropna(how="any")
    return out


def htf_bias_series(df: pd.DataFrame, htf_rule: str,
                    atr_period: int = 14, atr_mult: float = 2.5) -> pd.Series:
    """Compute HTF bias at each CTF bar — bias is updated when a new HTF
    monowave is confirmed.

    Returns Series aligned to df.index, values in {-2,-1,0,1,2}.
    """
    htf_df = resample_ohlc(df, htf_rule)
    htf_pivots = detect_monowaves(htf_df, atr_period=atr_period, atr_mult=atr_mult)

    # CRITICAL: pivot becomes "known" at its CONFIRMATION bar (when reversal
    # threshold was hit on HTF), NOT at the extremum bar. Using extremum bar
    # = look-ahead because we don't know it's a pivot until the reversal.
    pivot_ts = []
    for p in htf_pivots:
        idx = p.confirmation_idx if p.confirmation_idx >= 0 else p.idx
        pivot_ts.append(htf_df.index[idx])

    bias = pd.Series(0, index=df.index, dtype=int)
    if not htf_pivots:
        return bias

    # Walk through CTF index, maintain running bias
    p_iter = 0
    current_bias = 0
    confirmed_so_far: list[Pivot] = []
    for ts in df.index:
        # advance pivots whose confirmation happened ≤ ts
        while p_iter < len(htf_pivots) and pivot_ts[p_iter] <= ts:
            confirmed_so_far.append(htf_pivots[p_iter])
            current_bias = htf_bias_from_pivots(confirmed_so_far)
            p_iter += 1
        bias.loc[ts] = current_bias
    return bias
