"""Neely audit — exit-mechanism sweep on the flagship crypto/1d/wave3/long.

The target-map audit showed 78% of trades exit at the 12-bar timeout, not at a
Fibonacci target (TP1 reached only ~16% OOS). So the edge is favourable DRIFT of
the early third wave, not textbook fib-extension hitting. This script holds the
validated ENTRY and STOP fixed and sweeps a small set of PRINCIPLED exit
mechanisms, scoring each by net-of-cost EV on a 70/30 chronological split.

Discipline against overfitting:
  - few, principled variants (not a dense grid)
  - winner must beat the current baseline in BOTH train AND test
  - prefer the simplest variant within noise

Honest fill throughout: next_open entry, gap-realistic stop, cost subtracted.
Run: python scripts/audit_exit_sweep.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from ewb.monowaves import detect_monowaves                 # noqa: E402
from ewb.rules import classify_pivots                      # noqa: E402
from ewb.wave3 import detect_wave3_setups, TP_MULTS        # noqa: E402
from ewb.htf import structural_trend_series                # noqa: E402
from ewb.research.providers import download_binance_ohlc   # noqa: E402

INTERVAL, PERIOD = "1d", "1500d"
MAX_W1_FRAC, COMPASS_RULE = 0.50, "1W"
COST_RT = 2 * 0.0010 + 0.0005
CRYPTO = ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "ADA-USD", "AVAX-USD",
          "LINK-USD", "DOT-USD", "NEAR-USD", "INJ-USD", "AAVE-USD", "ATOM-USD",
          "LTC-USD", "XLM-USD", "OP-USD", "HBAR-USD", "FIL-USD", "TRX-USD"]


def _exit_target_timeout(r, target, timeout):
    """Fixed target + timeout. Gap-realistic stop. Gross return (long)."""
    hi, lo, op, cl, e, stop = r["hi"], r["lo"], r["op"], r["cl"], r["entry"], r["stop"]
    eb = r["eb"]; jend = min(len(cl), eb + 1 + timeout)
    for j in range(eb + 1, jend):
        if lo[j] <= stop:
            return (min(stop, op[j]) - e) / e
        if target is not None and hi[j] >= target:
            return (target - e) / e
    return (cl[jend - 1] - e) / e


def _exit_trail(r, trigger_R, timeout, lock_R=0.0):
    """After price reaches +trigger_R (in risk units), move stop up to
    entry+lock_R*risk and ride to timeout. Captures drift, caps downside.
    Gross return (long)."""
    hi, lo, op, cl, e, stop = r["hi"], r["lo"], r["op"], r["cl"], r["entry"], r["stop"]
    risk = e - stop
    eb = r["eb"]; jend = min(len(cl), eb + 1 + timeout)
    cur_stop = stop
    armed = False
    for j in range(eb + 1, jend):
        if lo[j] <= cur_stop:
            return (min(cur_stop, op[j]) - e) / e
        if not armed and hi[j] >= e + trigger_R * risk:
            cur_stop = e + lock_R * risk            # lock in (BE if lock_R=0)
            armed = True
    return (cl[jend - 1] - e) / e


# Exit variants: name -> callable(r) -> gross return.
VARIANTS = {
    "fib1.618_t12 (current)": lambda r: _exit_target_timeout(r, r["tp2"], 12),
    "fib1.618_t18":           lambda r: _exit_target_timeout(r, r["tp2"], 18),
    "fib1.618_t24":           lambda r: _exit_target_timeout(r, r["tp2"], 24),
    "R2_t12":                 lambda r: _exit_target_timeout(r, r["entry"] + 2*(r["entry"]-r["stop"]), 12),
    "R3_t12":                 lambda r: _exit_target_timeout(r, r["entry"] + 3*(r["entry"]-r["stop"]), 12),
    "R3_t18":                 lambda r: _exit_target_timeout(r, r["entry"] + 3*(r["entry"]-r["stop"]), 18),
    "timeout_only_t12":       lambda r: _exit_target_timeout(r, None, 12),
    "timeout_only_t18":       lambda r: _exit_target_timeout(r, None, 18),
    "trail_1R_BE_t18":        lambda r: _exit_trail(r, 1.0, 18, lock_R=0.0),
    "trail_2R_lock1R_t24":    lambda r: _exit_trail(r, 2.0, 24, lock_R=1.0),
}


def _entries_for(df):
    hi, lo, op, cl = (df["high"].values, df["low"].values,
                      df["open"].values, df["close"].values)
    piv = detect_monowaves(df, atr_mult=2.5)
    classify_pivots(piv)
    try:
        dt = pd.to_datetime(df["ts"], utc=True, errors="coerce")
        compass = structural_trend_series(df.set_index(dt), COMPASS_RULE).values
    except Exception:
        compass = None
    piv_sorted = sorted((p for p in piv if p.confirmation_idx >= 0),
                        key=lambda p: p.confirmation_idx)
    known, pp, seen, out = [], 0, set(), []
    for i in range(60, len(df) - 1):
        while pp < len(piv_sorted) and piv_sorted[pp].confirmation_idx <= i:
            known.append(piv_sorted[pp]); pp += 1
        if len(known) < 3:
            continue
        bias = int(compass[i]) if compass is not None and i < len(compass) else 0
        for s in detect_wave3_setups(known, float(cl[i]), i, max_w1_frac=MAX_W1_FRAC):
            if s.side != "long" or not (s.triggered and s.struct_ok and s.rr1 >= 1.0):
                continue
            if bias < 0:
                continue
            key = (round(s.entry_px, 4), round(s.stop_px, 4))
            if key in seen:
                continue
            seen.add(key)
            eb = i + 1
            entry = float(op[eb])
            if entry <= 0:
                continue
            w1 = abs(s.w1_end - s.w1_start)
            tp2 = entry + TP_MULTS[1] * w1
            risk = abs(entry - s.stop_px)
            if risk <= 0 or (tp2 - entry) / risk < 1.0:
                continue
            out.append({"ts": df["ts"].iloc[eb], "entry": entry, "stop": s.stop_px,
                        "tp2": tp2, "eb": eb, "hi": hi, "lo": lo, "op": op, "cl": cl})
    return out


def main():
    rows = []
    for tk in CRYPTO:
        df = download_binance_ohlc(tk, INTERVAL, PERIOD, min_rows=120)
        if df is None:
            continue
        df = df.reset_index(drop=False)
        df["ts"] = pd.to_datetime(df.iloc[:, 0], utc=True, errors="coerce")
        for e in _entries_for(df):
            rows.append(e)
    if not rows:
        print("No entries."); return

    ts = pd.to_datetime([r["ts"] for r in rows], utc=True)
    order = np.argsort(ts.values)
    rows = [rows[i] for i in order]; ts = ts[order]
    cut = ts[int(len(rows) * 0.70)]
    train = [r for r, t in zip(rows, ts) if t <= cut]
    test = [r for r, t in zip(rows, ts) if t > cut]

    def ev(sample, fn):
        if not sample:
            return float("nan"), float("nan"), 0
        a = np.array([fn(r) - COST_RT for r in sample])
        return a.mean() * 100, (a > 0).mean() * 100, len(a)

    base_tr = ev(train, VARIANTS["fib1.618_t12 (current)"])[0]
    base_te = ev(test, VARIANTS["fib1.618_t12 (current)"])[0]
    print(f"flagship crypto/1d/wave3/long | train n={len(train)} test n={len(test)}")
    print(f"baseline (fib1.618_t12): train EV={base_tr:+.2f}%  OOS EV={base_te:+.2f}%\n")
    print(f"{'variant':24}{'train EV%':>10}{'OOS EV%':>9}{'OOS WR%':>9}{'stable?':>9}")
    print("-" * 64)
    results = []
    for name, fn in VARIANTS.items():
        tr_ev, _, _ = ev(train, fn)
        te_ev, te_wr, te_n = ev(test, fn)
        stable = (tr_ev > base_tr) and (te_ev > base_te)
        results.append((name, tr_ev, te_ev, te_wr, stable))
        flag = "YES" if stable else ("=base" if name.startswith("fib1.618_t12") else "no")
        print(f"{name:24}{tr_ev:>9.2f}%{te_ev:>8.2f}%{te_wr:>8.0f}%{flag:>9}")

    winners = [r for r in results if r[4]]
    print()
    if winners:
        best = max(winners, key=lambda r: r[2])
        print(f"BEST stable exit: {best[0]}  OOS EV={best[2]:+.2f}% "
              f"(baseline {base_te:+.2f}%, +{best[2]-base_te:.2f}pp)")
    else:
        print("No variant beats baseline in BOTH train and test — keep single fib1.618_t12.")


if __name__ == "__main__":
    main()
