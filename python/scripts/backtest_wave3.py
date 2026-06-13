"""Backtest the EPIC-3 Wave-3 entry engine and emit a winrate LUT for the gate.

The Wave-3 entry (Neely Ch.5): enter on the break of the W1 end after a healthy
38-62% W2 pullback, stop at W2 end, target fib 1.618 x W1. This script replays
the setup over history and writes per-(asset_class, interval, fig_type, side)
NET expectancy to `ewb_wave3_backtest_grouped.parquet`, which the auto-trader's
gate uses.

HONEST accounting (EPIC-0/EPIC-1): fills at the live next_open (open[trigger+1]),
NOT the structural break level (which is in the past and inflated EV ~+3.6%);
stop fills are gap-realistic; and every trade is NET of round-trip cost (COST_RT).
Under honest accounting the cost-negative LTF-long groups correctly drop out —
only genuinely positive-net setups survive the train+test stability filter.

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
from ewb.htf import structural_trend_series         # noqa: E402
from ewb.research.providers import download_binance_ohlc  # noqa: E402

CACHE_DIR = ROOT / "python" / "data" / "ohlc_cache" / "tiingo"
OUT = ROOT / "brain-output" / "backtests" / "ewb_wave3_backtest_grouped.parquet"
# Mirror the LIVE wave3 policy per timeframe so the LUT validates the SAME trade
# population the auto-trader takes. Keep in lockstep with:
#   scan_probability_signals._W3_MAX_W1_FRAC / _W3_HTF_RULE
#   auto_trader.TIMEOUT_BY_TF / BIASFLIP_RULE / BIASFLIP_MODE
TIMEOUT_BY_TF = {"1h": 24, "4h": 18, "1d": 12}
MAX_W1_FRAC_BY_TF = {"1h": 0.15, "4h": 0.30, "1d": 0.50}
COMPASS_RULE_BY_TF = {"1h": "1D", "4h": "1D", "1d": "1W"}
# bias-flip exit, mirroring auto_trader: close when the HTF compass turns against
# the position. "strong" = |bias|=2 against, "sign" = any opposing sign, "off".
BIASFLIP_MODE = os.environ.get("EWB_BIASFLIP_MODE", "strong").lower()
# Round-trip trading cost as a fraction of notional (fee*2 sides + spread), so
# the LUT carries NET expectancy. Crypto spot taker ~0.10%/side + ~5bp spread;
# liquid stock ~0.01%/side + ~2bp. Without this the LUT trades cost-negative
# setups (audit EPIC-0: crypto 1h/4h long are net-negative after costs).
COST_RT = {"crypto": 2 * 0.0010 + 0.0005, "stock": 2 * 0.0001 + 0.0002}
# Stocks: 1d only (no long-history intraday cache — Tiingo rate limits). Crypto:
# multi-TF via keyless Binance. Periods balance sample size against compute.
CRYPTO_INTERVALS = [("1h", "365d"), ("4h", "730d"), ("1d", "1500d")]
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
    out = df[need + ["ts"]].dropna(subset=need).reset_index(drop=True)
    return out if len(out) > 120 else None


def _flipped(bias: int, up: bool) -> bool:
    """bias-flip condition mirroring auto_trader.bias_flip_exit."""
    if BIASFLIP_MODE == "off":
        return False
    if BIASFLIP_MODE == "sign":
        return (bias < 0) if up else (bias > 0)
    return (bias <= -2) if up else (bias >= 2)   # "strong"


def _sim_exit(df: pd.DataFrame, entry_bar: int, entry: float, stop: float,
              target: float, up: bool, timeout: int,
              compass=None) -> float | None:
    """Signed GROSS fractional return. Entry is already filled at entry_bar's open
    (next_open execution); exit at the EARLIEST of SL, TP, bias-flip, or timeout.
    Stop fill is gap-realistic (worse-of stop vs the gap open); TP fills at the
    level; bias-flip / timeout at the bar close. Mirrors live try_close_trades."""
    hi = df["high"].values
    lo = df["low"].values
    op = df["open"].values
    cl = df["close"].values
    end = min(len(df), entry_bar + 1 + timeout)
    for j in range(entry_bar + 1, end):
        if up:
            if lo[j] <= stop:
                fill = min(stop, op[j])           # gap through stop -> worse fill
                return (fill - entry) / entry
            if hi[j] >= target:
                return (target - entry) / entry
        else:
            if hi[j] >= stop:
                fill = max(stop, op[j])
                return (entry - fill) / entry
            if lo[j] <= target:
                return (entry - target) / entry
        if compass is not None and j < len(compass) and _flipped(int(compass[j]), up):
            return (cl[j] - entry) / entry if up else (entry - cl[j]) / entry
    if end - 1 <= entry_bar:
        return None
    ex = cl[end - 1]
    return (ex - entry) / entry if up else (entry - ex) / entry


def _compass_series(df: pd.DataFrame, rule: str):
    """HTF structural compass per bar — mirrors the live wave3 gate. The backtest
    df has an integer index, so rebuild a ts-indexed view for resampling. Returns
    a numpy array aligned to df rows, or None on failure (no gating)."""
    try:
        dt = pd.to_datetime(df["ts"], utc=True, errors="coerce")
        df_dt = df.set_index(dt)
        return structural_trend_series(df_dt, rule).values
    except Exception as exc:  # pragma: no cover - defensive
        print(f"  WARN: compass failed ({exc}) — gate disabled for this series")
        return None


def _w3_trades(df: pd.DataFrame, interval: str, asset_class: str) -> list[dict]:
    timeout = TIMEOUT_BY_TF.get(interval, 12)
    frac = MAX_W1_FRAC_BY_TF.get(interval, 0.50)
    rule = COMPASS_RULE_BY_TF.get(interval, "1W")
    cost = COST_RT.get(asset_class, 0.0)
    opens = df["open"].values
    piv = detect_monowaves(df, atr_mult=2.5)
    classify_pivots(piv)
    compass = _compass_series(df, rule)
    # O(n) growing-known pointer (the per-bar list comprehension was O(n²) and
    # hangs on long 1h history).
    piv_sorted = sorted((p for p in piv if p.confirmation_idx >= 0),
                        key=lambda p: p.confirmation_idx)
    known: list = []
    pp = 0
    seen: set = set()
    out: list[dict] = []
    for i in range(60, len(df)):
        while pp < len(piv_sorted) and piv_sorted[pp].confirmation_idx <= i:
            known.append(piv_sorted[pp])
            pp += 1
        bias = int(compass[i]) if compass is not None and i < len(compass) else 0
        if len(known) < 3:
            continue
        for s in detect_wave3_setups(known, float(df["close"].iloc[i]), i,
                                     max_w1_frac=frac):
            if not (s.triggered and s.struct_ok and s.rr1 >= 1.0):
                continue
            # HTF compass gate (with-trend only) — mirror live scan.
            if bias > 0 and s.side == "short":
                continue
            if bias < 0 and s.side == "long":
                continue
            key = (round(s.entry_px, 4), round(s.stop_px, 4))
            if key in seen:
                continue
            seen.add(key)
            up = s.side == "long"
            # next_open fill: enter at the open of the bar AFTER detection (live
            # parity). Structural stop/target levels are unchanged.
            entry_bar = i + 1
            if entry_bar >= len(df):
                continue
            entry_px = float(opens[entry_bar])
            if entry_px <= 0:
                continue
            # Re-validate R:R from the ACTUAL fill (live does this); skip if the
            # next_open overshot the structural level and R:R fell below 1.
            risk = abs(entry_px - s.stop_px)
            reward = abs(s.primary_tp - entry_px)
            if risk <= 0 or reward / risk < 1.0:
                continue
            gross = _sim_exit(df, entry_bar, entry_px, s.stop_px, s.primary_tp, up,
                              timeout, compass)
            if gross is None:
                continue
            ret = gross - cost                         # NET of round-trip cost
            ts = df["ts"].iloc[entry_bar] if "ts" in df.columns else pd.NaT
            out.append({"side": s.side, "win": ret > 0, "ret": ret, "entry_ts": ts})
    return out


def main() -> None:
    if os.environ.get("EWB_WAVE3") != "1":
        os.environ["EWB_WAVE3"] = "1"
    rows: list[dict] = []

    # Stocks: 1d only (long-history cache).
    for f in sorted(glob.glob(str(CACHE_DIR / "*_1d_5y.parquet"))):
        df = _load_cached(f)
        if df is None:
            continue
        for t in _w3_trades(df, "1d", "stock"):
            t.update(asset_class="stock", interval="1d", fig_type="wave3")
            rows.append(t)

    # Crypto: 1h / 4h / 1d via keyless Binance.
    for tk in CRYPTO:
        for interval, period in CRYPTO_INTERVALS:
            df = download_binance_ohlc(tk, interval, period, min_rows=120)
            if df is None:
                continue
            df["ts"] = pd.to_datetime(df.index, utc=True, errors="coerce")
            df = df.reset_index(drop=True)
            for t in _w3_trades(df, interval, "crypto"):
                t.update(asset_class="crypto", interval=interval, fig_type="wave3")
                rows.append(t)

    d = pd.DataFrame(rows)
    if d.empty:
        print("No W3 trades found — nothing written.")
        return

    # Out-of-sample: chronological 70/30 split PER GROUP; LUT uses TEST metrics.
    # Per-group (not global) so high-frequency 1h/4h trades don't pull the global
    # cutoff recent and starve 1d groups of test samples.
    d["entry_ts"] = pd.to_datetime(d["entry_ts"], utc=True, errors="coerce", format="mixed")
    d = d.dropna(subset=["entry_ts"]).sort_values("entry_ts")
    keys = ["asset_class", "interval", "fig_type", "side"]

    cut = d.groupby(keys)["entry_ts"].transform(lambda s: s.quantile(0.70))
    d["_oos"] = d["entry_ts"] > cut
    train, test = d[~d["_oos"]], d[d["_oos"]]

    def grp(frame):
        return (frame.groupby(keys)
                .agg(trades=("win", "size"), winrate=("win", "mean"),
                     expectancy=("ret", "mean")).reset_index())

    g_test, g_train = grp(test), grp(train)
    m = g_test.merge(g_train, on=keys, how="left", suffixes=("_oos", "_is"))
    # Stability filter: positive in BOTH train and test (excludes lucky-test and
    # in-sample-only edges). LUT carries OOS (test) metrics for survivors.
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
    print(f"W3 backtest: {len(d)} trades; per-group 70/30 split "
          f"(train {len(train)} / test {len(test)})\nSTABLE = positive in BOTH train+test (LUT only these):\n")
    print(m.sort_values("expectancy_oos", ascending=False)[
        ["asset_class", "interval", "fig_type", "side", "trades_oos", "OOS_WR%", "OOS_EV%", "IS_EV%", "STABLE"]
    ].to_string(index=False))
    print(f"\nWrote {OUT}: {len(lut)} stable setups (OOS metrics)")


if __name__ == "__main__":
    main()
