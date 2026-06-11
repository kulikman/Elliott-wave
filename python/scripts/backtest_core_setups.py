"""Backtest Neely "core" setups and emit a reward-first LUT for the gate.

Core setups (neely_core_ab_backtest.neely_core_setups): post-W4 impulse
pullback, triangle thrust, zigzag C=A, moving-correction follow. Each is
replayed over history (cached stock OHLC + Binance crypto), exits simulated
with costs, and grouped per (asset_class, interval, fig_type, side) into
`ewb_core_backtest_grouped.parquet`. The auto-trader's reward-first gate merges
this LUT and selects by expectancy — so the profitable ones (e.g. triangle
thrust crypto 4h long, +0.8-1.3%/trade) trade and thin scalps (post-W4,
+0.35%) are dropped by the EV floor.

Run: python scripts/backtest_core_setups.py
"""
from __future__ import annotations

import glob
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from ewb.monowaves import detect_monowaves               # noqa: E402
from ewb.rules import classify_pivots                    # noqa: E402
from ewb.figures import match_figures                    # noqa: E402
from ewb.research import cost_for                         # noqa: E402
from ewb.research.providers import download_binance_ohlc  # noqa: E402
from scripts.neely_core_ab_backtest import (              # noqa: E402
    neely_core_setups, entry_index, simulate_level_exit,
)

CACHE_DIR = ROOT / "python" / "data" / "ohlc_cache" / "tiingo"
OUT = ROOT / "brain-output" / "backtests" / "ewb_core_backtest_grouped.parquet"
EXIT_BARS = 30
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
    out = df[need].dropna()
    return out if len(out) > 120 else None


def _core_trades(df: pd.DataFrame, ticker: str, interval: str) -> list[dict]:
    piv = detect_monowaves(df, atr_mult=2.5)
    classify_pivots(piv)
    figs = [f for f in match_figures(piv) if f.confirmed and f.pivots]
    cost = cost_for(ticker)
    out: list[dict] = []
    for fig in figs:
        e_idx = entry_index(fig)
        if e_idx < 0 or e_idx + 1 >= len(df):
            continue
        entry_px = float(df["close"].iloc[e_idx])
        for s in neely_core_setups(fig):
            side = s["side"]
            if "target" in s and "stop" in s:
                target, stop = s["target"], s["stop"]
            elif "target_offset" in s:
                target = entry_px + s["target_offset"]
                stop = entry_px + s["stop_offset"]
            else:
                continue
            r = simulate_level_exit(df, e_idx, side, target, stop, EXIT_BARS, cost)
            if r is None:
                continue
            out.append({"fig_type": s["setup"], "side": side,
                        "win": r["win"], "net_ret": r["net_ret"]})
    return out


def main() -> None:
    rows: list[dict] = []
    for f in sorted(glob.glob(str(CACHE_DIR / "*_1d_5y.parquet"))):
        df = _load_cached(f)
        if df is None:
            continue
        for t in _core_trades(df.reset_index(drop=True), Path(f).stem.split("_")[0], "1d"):
            t.update(asset_class="stock", interval="1d")
            rows.append(t)
    # crypto: 1d and 4h (triangle thrust validated on 4h)
    for tk in CRYPTO:
        for interval, period in (("1d", "1500d"), ("4h", "900d")):
            df = download_binance_ohlc(tk, interval, period, min_rows=120)
            if df is None:
                continue
            for t in _core_trades(df.reset_index(drop=True), tk, interval):
                t.update(asset_class="crypto", interval=interval)
                rows.append(t)

    d = pd.DataFrame(rows)
    if d.empty:
        print("No core trades found.")
        return
    grouped = (
        d.groupby(["asset_class", "interval", "fig_type", "side"])
        .agg(trades=("win", "size"), winrate=("win", "mean"),
             expectancy=("net_ret", "mean"))
        .reset_index()
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    grouped.to_parquet(OUT, index=False)

    show = grouped[grouped["trades"] >= 20].copy()
    show["WR%"] = (show["winrate"] * 100).round(0)
    show["EV%"] = (show["expectancy"] * 100).round(2)
    print(f"Core backtest: {len(d)} trades across {grouped['fig_type'].nunique()} setups")
    print(show.sort_values("expectancy", ascending=False)[
        ["asset_class", "interval", "fig_type", "side", "trades", "WR%", "EV%"]
    ].to_string(index=False))
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
