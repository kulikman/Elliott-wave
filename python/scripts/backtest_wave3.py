"""Backtest the EPIC-3 Wave-3 entry engine and emit a winrate LUT for the gate.

The Wave-3 entry (Neely Ch.5) is the strongest structural trade: enter on the
break of the W1 end after a healthy 38-62% W2 pullback, stop at W2 end, target
the Neely channel projection (or fib 1.618 x W1). This script replays that
setup over history and writes per-(asset_class, interval, fig_type, side)
winrates to `ewb_wave3_backtest_grouped.parquet`, which the auto-trader's
high-winrate gate merges with the main flat LUT so validated W3 setups can
trade. Unlike double_corr, W3 has large samples and real positive expectancy.

Data: cached stock OHLC under python/data/ohlc_cache/tiingo (avoids Tiingo
rate limits) + Binance for crypto. Output is grouped winrates; the live gate
still enforces WR>=55%, n>=20, freshness and time-budget on top.

Run: EWB_WAVE3=1 python scripts/backtest_wave3.py
"""
from __future__ import annotations

import glob
import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from ewb.monowaves import detect_monowaves          # noqa: E402
from ewb.rules import classify_pivots               # noqa: E402
from ewb.wave3 import detect_wave3_setups           # noqa: E402
from ewb.research.providers import download_binance_ohlc  # noqa: E402

CACHE_DIR = ROOT / "python" / "data" / "ohlc_cache" / "tiingo"
OUT = ROOT / "brain-output" / "backtests" / "ewb_wave3_backtest_grouped.parquet"
TIMEOUT_BARS = 30
CRYPTO = ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "ADA-USD", "AVAX-USD",
          "LINK-USD", "DOT-USD", "NEAR-USD", "INJ-USD", "AAVE-USD", "ATOM-USD",
          "LTC-USD", "XLM-USD", "OP-USD", "HBAR-USD", "FIL-USD", "TRX-USD"]


def _load_cached(path: str) -> pd.DataFrame | None:
    df = pd.read_parquet(path)
    if "date" in df.columns:
        df = df.set_index("date")
    df.columns = [str(c).lower() for c in df.columns]
    need = ["open", "high", "low", "close"]
    if not set(need).issubset(df.columns):
        return None
    out = df[need].dropna().reset_index(drop=True)
    return out if len(out) > 120 else None


def _sim_exit(df: pd.DataFrame, i: int, entry: float, stop: float,
              target: float, up: bool) -> float | None:
    hi = df["high"].values
    lo = df["low"].values
    cl = df["close"].values
    end = min(len(df), i + 1 + TIMEOUT_BARS)
    for j in range(i + 1, end):
        if up:
            if lo[j] <= stop:
                return stop
            if hi[j] >= target:
                return target
        else:
            if hi[j] >= stop:
                return stop
            if lo[j] <= target:
                return target
    return cl[end - 1] if end - 1 > i else None


def _w3_trades(df: pd.DataFrame) -> list[dict]:
    piv = detect_monowaves(df, atr_mult=2.5)
    classify_pivots(piv)
    seen: set = set()
    out: list[dict] = []
    for i in range(60, len(df)):
        known = [p for p in piv if 0 <= p.confirmation_idx <= i]
        if len(known) < 3:
            continue
        for s in detect_wave3_setups(known, float(df["close"].iloc[i]), i):
            if not (s.triggered and s.struct_ok and s.rr1 >= 1.0):
                continue
            key = (round(s.entry_px, 4), round(s.stop_px, 4))
            if key in seen:
                continue
            seen.add(key)
            up = s.side == "long"
            px = _sim_exit(df, i, s.entry_px, s.stop_px, s.primary_tp, up)
            if px is None:
                continue
            ret = (px - s.entry_px) / s.entry_px * (1.0 if up else -1.0)
            out.append({"side": s.side, "win": ret > 0, "ret": ret})
    return out


def main() -> None:
    if os.environ.get("EWB_WAVE3") != "1":
        os.environ["EWB_WAVE3"] = "1"
    rows: list[dict] = []

    for f in sorted(glob.glob(str(CACHE_DIR / "*_1d_5y.parquet"))):
        df = _load_cached(f)
        if df is None:
            continue
        for t in _w3_trades(df):
            t.update(asset_class="stock", interval="1d", fig_type="wave3")
            rows.append(t)

    for tk in CRYPTO:
        df = download_binance_ohlc(tk, "1d", "1500d", min_rows=120)
        if df is None:
            continue
        df = df.reset_index(drop=True)
        for t in _w3_trades(df):
            t.update(asset_class="crypto", interval="1d", fig_type="wave3")
            rows.append(t)

    d = pd.DataFrame(rows)
    if d.empty:
        print("No W3 trades found — nothing written.")
        return

    grouped = (
        d.groupby(["asset_class", "interval", "fig_type", "side"])
        .agg(trades=("win", "size"), winrate=("win", "mean"),
             expectancy=("ret", "mean"))
        .reset_index()
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    grouped.to_parquet(OUT, index=False)

    print(f"W3 backtest: {len(d)} trades, overall WR {d['win'].mean()*100:.0f}%, "
          f"avg {d['ret'].mean()*100:+.2f}%/trade")
    show = grouped.copy()
    show["winrate"] = (show["winrate"] * 100).round(0)
    show["expectancy"] = (show["expectancy"] * 100).round(2)
    print(show.to_string(index=False))
    passing = grouped[(grouped["winrate"] >= 0.55) & (grouped["trades"] >= 20)]
    print(f"\nGate-passing groups (WR>=55%, n>=20): {len(passing)}")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
