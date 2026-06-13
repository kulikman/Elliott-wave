"""EPIC-0 — Edge reality check (cost-aware, honest fill, random baseline).

Answers ONE question before any other remediation work: does the wave3 edge
survive (a) the live next_open entry fill, (b) realistic trading costs, and
(c) a random-timing control? If a group's net EV <= its random baseline, the
Neely wave detection adds nothing there and polishing it is premature.

Honesty rules applied here (stricter than backtest_wave3.py):
  - Entry = open[trigger_bar+1] (live next_open), NOT the structural break level.
  - Stop fill is gap-realistic: long SL = min(stop, open[j]); short SL = max(...).
  - TP fill stays at the target level (we do NOT credit favourable gaps).
  - Round-trip cost (fee*2 + spread) subtracted from every trade's return.
  - Random control: same side / stop% / target% / timeout as each real wave3
    entry, but entered at a RANDOM bar — isolates timing edge from risk geometry.

Read-only: touches no LUT. Run: python scripts/edge_reality_check.py
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from ewb.monowaves import detect_monowaves                 # noqa: E402
from ewb.rules import classify_pivots                      # noqa: E402
from ewb.wave3 import detect_wave3_setups                  # noqa: E402
from ewb.research.providers import download_binance_ohlc   # noqa: E402

random.seed(42)
np.random.seed(42)

# Round-trip cost as a fraction of notional (fee*2 sides + spread). Crypto spot
# taker ~0.10%/side on Binance; stock ~0.01%/side. Spread ~5bp crypto / 2bp liquid stock.
COST_RT = {"crypto": 2 * 0.0010 + 0.0005, "stock": 2 * 0.0001 + 0.0002}

TIMEOUT_BY_TF = {"1h": 24, "4h": 18, "1d": 12}
MAX_W1_FRAC = {"1h": 0.15, "4h": 0.30, "1d": 0.50}

# Representative universe (enough for a verdict; expand later if it survives).
CRYPTO = ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "ADA-USD", "AVAX-USD",
          "LINK-USD", "DOT-USD"]
CRYPTO_INTERVALS = [("1h", "365d"), ("4h", "730d"), ("1d", "1500d")]
STOCK_CACHE = ROOT / "python" / "data" / "ohlc_cache" / "tiingo"


def _sim(df, i_entry, entry, stop, target, up, timeout):
    """Gap-realistic exit sim starting at the entry bar's NEXT bar. Returns gross
    fractional return (signed for side), or None if no usable history."""
    hi, lo, op, cl = (df["high"].values, df["low"].values,
                      df["open"].values, df["close"].values)
    end = min(len(df), i_entry + 1 + timeout)
    for j in range(i_entry + 1, end):
        if up:
            if lo[j] <= stop:
                fill = min(stop, op[j])          # gap through stop -> worse
                return (fill - entry) / entry
            if hi[j] >= target:
                return (target - entry) / entry
        else:
            if hi[j] >= stop:
                fill = max(stop, op[j])
                return (entry - fill) / entry
            if lo[j] <= target:
                return (entry - target) / entry
    if end - 1 <= i_entry:
        return None
    exit_px = cl[end - 1]
    return (exit_px - entry) / entry if up else (entry - exit_px) / entry


def _wave3_entries(df, interval):
    """Real wave3 entries with HONEST next_open fill. Returns list of dicts."""
    frac = MAX_W1_FRAC.get(interval, 0.5)
    timeout = TIMEOUT_BY_TF.get(interval, 12)
    piv = detect_monowaves(df, atr_mult=2.5)
    classify_pivots(piv)
    piv_sorted = sorted((p for p in piv if p.confirmation_idx >= 0),
                        key=lambda p: p.confirmation_idx)
    known, pp, seen, out = [], 0, set(), []
    op = df["open"].values
    for i in range(60, len(df) - 1):
        while pp < len(piv_sorted) and piv_sorted[pp].confirmation_idx <= i:
            known.append(piv_sorted[pp]); pp += 1
        if len(known) < 3:
            continue
        for s in detect_wave3_setups(known, float(df["close"].iloc[i]), i, max_w1_frac=frac):
            if not (s.triggered and s.struct_ok and s.rr1 >= 1.0):
                continue
            k = (round(s.entry_px, 6), round(s.stop_px, 6))
            if k in seen:
                continue
            seen.add(k)
            up = s.side == "long"
            entry = float(op[i + 1])                       # next_open fill
            if entry <= 0:
                continue
            stop_pct = abs(entry - s.stop_px) / entry
            tgt_pct = abs(s.primary_tp - entry) / entry
            if tgt_pct <= 0 or stop_pct <= 0:
                continue
            ret = _sim(df, i + 1, entry, s.stop_px, s.primary_tp, up, timeout)
            if ret is None:
                continue
            out.append({"i": i, "side": s.side, "up": up,
                        "stop_pct": stop_pct, "tgt_pct": tgt_pct, "ret": ret})
    return out


def _random_control(df, entries, interval):
    """For each real entry: same side/stop%/target%/timeout, RANDOM entry bar."""
    timeout = TIMEOUT_BY_TF.get(interval, 12)
    op = df["open"].values
    n = len(df)
    rets = []
    for e in entries:
        r = random.randint(60, max(61, n - timeout - 2))
        entry = float(op[r + 1]) if r + 1 < n else None
        if not entry or entry <= 0:
            continue
        up = e["up"]
        stop = entry * (1 - e["stop_pct"]) if up else entry * (1 + e["stop_pct"])
        target = entry * (1 + e["tgt_pct"]) if up else entry * (1 - e["tgt_pct"])
        ret = _sim(df, r + 1, entry, stop, target, up, timeout)
        if ret is not None:
            rets.append(ret)
    return rets


def _agg(rets, cost):
    if not rets:
        return None
    a = np.array(rets)
    return {"n": len(a), "gross": a.mean(), "net": a.mean() - cost,
            "wr": float((a > 0).mean())}


def main():
    rows = []
    daily_returns = {}   # for correlation proxy

    # crypto multi-TF
    for tk in CRYPTO:
        for interval, period in CRYPTO_INTERVALS:
            df = download_binance_ohlc(tk, interval, period, min_rows=120)
            if df is None:
                continue
            df = df.reset_index(drop=True)
            if interval == "1d":
                daily_returns[tk] = df["close"].pct_change().dropna().values
            ents = _wave3_entries(df, interval)
            for side in ("long", "short"):
                real = [e for e in ents if e["side"] == side]
                if len(real) < 10:
                    continue
                ctrl = _random_control(df, real, interval)
                rows.append({"asset": "crypto", "tf": interval, "side": side,
                             "real": _agg([e["ret"] for e in real], COST_RT["crypto"]),
                             "rand": _agg(ctrl, COST_RT["crypto"])})

    # stocks 1d from cache
    for f in sorted(STOCK_CACHE.glob("*_1d_5y.parquet")):
        df = pd.read_parquet(f)
        if "date" in df.columns:
            df = df.set_index("date")
        df.columns = [str(c).lower() for c in df.columns]
        if not {"open", "high", "low", "close"}.issubset(df.columns):
            continue
        df = df.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)
        if len(df) < 200:
            continue
        ents = _wave3_entries(df, "1d")
        for side in ("long", "short"):
            real = [e for e in ents if e["side"] == side]
            if len(real) < 5:
                continue
            ctrl = _random_control(df, real, "1d")
            rows.append({"asset": "stock", "tf": "1d", "side": side,
                         "real": _agg([e["ret"] for e in real], COST_RT["stock"]),
                         "rand": _agg(ctrl, COST_RT["stock"]), "ticker": f.name})

    # ── aggregate by group across tickers ──
    agg = {}
    for r in rows:
        key = (r["asset"], r["tf"], r["side"])
        agg.setdefault(key, {"real": [], "rand": []})
        if r["real"]:
            agg[key]["real"].append(r["real"])
        if r["rand"]:
            agg[key]["rand"].append(r["rand"])

    def _pool(lst):
        if not lst:
            return None
        N = sum(x["n"] for x in lst)
        if N == 0:
            return None
        gross = sum(x["gross"] * x["n"] for x in lst) / N
        net = sum(x["net"] * x["n"] for x in lst) / N
        wr = sum(x["wr"] * x["n"] for x in lst) / N
        return {"n": N, "gross": gross, "net": net, "wr": wr}

    print("\n=== EDGE REALITY CHECK (honest next_open fill + costs + random baseline) ===")
    print(f"{'group':22} {'n':>5} {'gross%':>8} {'net%':>8} {'WR':>5} | "
          f"{'rand_net%':>9} {'EDGE vs rand':>12}")
    print("-" * 78)
    verdict = []
    for key in sorted(agg):
        real = _pool(agg[key]["real"])
        rand = _pool(agg[key]["rand"])
        if not real:
            continue
        g = key[0] + "/" + key[1] + "/" + key[2]
        rn = rand["net"] * 100 if rand else float("nan")
        edge = (real["net"] - (rand["net"] if rand else 0)) * 100
        flag = "OK" if (real["net"] > 0 and edge > 0) else ("DEAD" if real["net"] <= 0 else "~rand")
        print(f"{g:22} {real['n']:>5} {real['gross']*100:>8.2f} {real['net']*100:>8.2f} "
              f"{real['wr']*100:>4.0f}% | {rn:>9.2f} {edge:>+10.2f}pp  {flag}")
        verdict.append((g, real["net"] * 100, edge, flag))

    # ── crypto correlation proxy ──
    print("\n=== PORTFOLIO CORRELATION (crypto 1d daily returns) ===")
    keys = [k for k in daily_returns if len(daily_returns[k]) > 100]
    if len(keys) >= 2:
        L = min(len(daily_returns[k]) for k in keys)
        M = np.vstack([daily_returns[k][-L:] for k in keys])
        C = np.corrcoef(M)
        iu = np.triu_indices(len(keys), 1)
        print(f"tickers: {keys}")
        print(f"avg pairwise corr: {C[iu].mean():.2f}  (1.0 = one bet; high corr "
              f"=> 'many entries' is NOT diversification)")

    print("\n=== VERDICT ===")
    survivors = [v for v in verdict if v[3] == "OK"]
    print(f"Groups surviving costs AND beating random: {len(survivors)} / {len(verdict)}")
    for g, net, edge, flag in survivors:
        print(f"  SURVIVES: {g}  net {net:+.2f}%  edge vs random {edge:+.2f}pp")
    if not survivors:
        print("  NONE survive — wave3 net edge is not distinguishable from random timing.")


if __name__ == "__main__":
    main()
