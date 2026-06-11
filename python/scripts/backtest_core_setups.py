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
    df["ts"] = pd.to_datetime(df.index, utc=True, errors="coerce")
    out = df[need + ["ts"]].dropna(subset=need)
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
            ts = df["ts"].iloc[e_idx] if "ts" in df.columns else pd.NaT
            out.append({"fig_type": s["setup"], "side": side,
                        "win": r["win"], "net_ret": r["net_ret"], "entry_ts": ts})
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
            df["ts"] = pd.to_datetime(df.index, utc=True, errors="coerce")
            for t in _core_trades(df.reset_index(drop=True), tk, interval):
                t.update(asset_class="crypto", interval=interval)
                rows.append(t)

    d = pd.DataFrame(rows)
    if d.empty:
        print("No core trades found.")
        return

    # Out-of-sample validation: chronological 70/30 split. Train on the first
    # 70% of trades by entry time, validate on the held-out last 30%. The LUT
    # uses TEST (OOS) metrics so the gate never trades on in-sample-only edge.
    d["entry_ts"] = pd.to_datetime(d["entry_ts"], utc=True, errors="coerce", format="mixed")
    d = d.dropna(subset=["entry_ts"]).sort_values("entry_ts")
    cutoff = d["entry_ts"].quantile(0.70)
    train, test = d[d["entry_ts"] <= cutoff], d[d["entry_ts"] > cutoff]
    keys = ["asset_class", "interval", "fig_type", "side"]

    def grp(frame):
        return (frame.groupby(keys)
                .agg(trades=("win", "size"), winrate=("win", "mean"),
                     expectancy=("net_ret", "mean")).reset_index())

    g_test, g_train = grp(test), grp(train)
    m = g_test.merge(g_train, on=keys, how="left", suffixes=("_oos", "_is"))
    # Stability filter: the edge must be positive in BOTH train and test, so a
    # setup that only "works" on a lucky test slice (or only in-sample) is
    # excluded. The LUT carries OOS (test) metrics for the survivors.
    stable = m[(m["expectancy_oos"] > 0) & (m["expectancy_is"] > 0)].copy()
    lut = (stable[keys + ["trades_oos", "winrate_oos", "expectancy_oos"]]
           .rename(columns={"trades_oos": "trades", "winrate_oos": "winrate",
                            "expectancy_oos": "expectancy"}))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    lut.to_parquet(OUT, index=False)

    m["OOS_WR%"] = (m["winrate_oos"] * 100).round(0)
    m["OOS_EV%"] = (m["expectancy_oos"] * 100).round(2)
    m["IS_EV%"] = (m["expectancy_is"] * 100).round(2)
    m["STABLE"] = (m["expectancy_oos"] > 0) & (m["expectancy_is"] > 0)
    print(f"Core backtest: {len(d)} trades; split @ {str(cutoff)[:10]} "
          f"(train {len(train)} / test {len(test)})")
    print("STABLE = positive in BOTH train and test (only these enter the LUT):\n")
    print(m[m["trades_oos"] >= 20].sort_values("expectancy_oos", ascending=False)[
        ["asset_class", "interval", "fig_type", "side", "trades_oos", "OOS_WR%", "OOS_EV%", "IS_EV%", "STABLE"]
    ].to_string(index=False))
    print(f"\nWrote {OUT}: {len(lut)} stable setups (OOS metrics)")


if __name__ == "__main__":
    main()
