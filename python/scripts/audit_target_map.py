"""Neely strategy audit — target-probability map + scaled-exit EV.

Phase 1 (flagship setup crypto/1d/wave3/long): for every honest wave3 entry
in history, measure how often price reaches each Fibonacci extension target
(TP1=1.0xW1, TP2=1.618x, TP3=2.618x) BEFORE the stop or timeout, then compute
whether a probability-weighted SCALED exit (partial out at each target, stop to
breakeven after TP1) beats the current single-target exit — net of cost, OOS.

Honest accounting (mirrors backtest_wave3.py EPIC-0/1):
  - next_open fill: entry = open[trigger_bar+1]
  - gap-realistic stop: long SL fill = min(stop, open[j])
  - round-trip cost subtracted
  - HTF compass gate (with-trend only), same max_w1_frac as live

Read-only on LUT. Run: python scripts/audit_target_map.py
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

# Flagship setup parameters (mirror live crypto/1d).
INTERVAL = "1d"
PERIOD = "1500d"
TIMEOUT = 12
MAX_W1_FRAC = 0.50
COMPASS_RULE = "1W"
COST_RT = 2 * 0.0010 + 0.0005          # crypto round-trip
CRYPTO = ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "ADA-USD", "AVAX-USD",
          "LINK-USD", "DOT-USD", "NEAR-USD", "INJ-USD", "AAVE-USD", "ATOM-USD",
          "LTC-USD", "XLM-USD", "OP-USD", "HBAR-USD", "FIL-USD", "TRX-USD"]

# Candidate scaled-exit weight schemes (w1 at TP1, w2 at TP2, w3 at TP3).
WEIGHT_SCHEMES = {
    "single_TP2":   (0.0, 1.0, 0.0),    # current behaviour proxy (all at 1.618)
    "50/30/20":     (0.5, 0.3, 0.2),
    "40/35/25":     (0.4, 0.35, 0.25),
    "60/30/10":     (0.6, 0.3, 0.1),
    "34/33/33":     (1/3, 1/3, 1/3),
}


def _reach_map(hi, lo, j0, jend, stop, tp1, tp2, tp3, up):
    """With the ORIGINAL stop held, which targets are touched before the stop?
    Conservative (stop-first within a bar). Returns (reached1, reached2, reached3,
    stopped, mfe_frac) where mfe is the max favourable excursion fraction."""
    reached = [False, False, False]
    stopped = False
    mfe = 0.0
    entry_ref = None
    for j in range(j0, jend):
        if up:
            if lo[j] <= stop:
                stopped = True
                break
            for k, tp in enumerate((tp1, tp2, tp3)):
                if hi[j] >= tp:
                    reached[k] = True
        else:
            if hi[j] >= stop:
                stopped = True
                break
            for k, tp in enumerate((tp1, tp2, tp3)):
                if lo[j] <= tp:
                    reached[k] = True
    return reached[0], reached[1], reached[2], stopped


def _sim_single(hi, lo, op, cl, j0, jend, entry, stop, target, up):
    """Single-target exit (current behaviour). Gap-realistic stop. Gross return."""
    for j in range(j0, jend):
        if up:
            if lo[j] <= stop:
                return (min(stop, op[j]) - entry) / entry
            if hi[j] >= target:
                return (target - entry) / entry
        else:
            if hi[j] >= stop:
                return (entry - max(stop, op[j])) / entry
            if lo[j] <= target:
                return (entry - target) / entry
    ex = cl[jend - 1]
    return (ex - entry) / entry if up else (entry - ex) / entry


def _sim_scaled(hi, lo, op, cl, j0, jend, entry, stop, tp1, tp2, tp3,
                w1, w2, w3, up):
    """Scaled exit: partial out at each target; after TP1 the stop on the
    REMAINING position trails to breakeven (entry). Gap-realistic. Gross blended
    return (signed for side, fraction of full notional)."""
    remaining = 1.0
    realized = 0.0
    cur_stop = stop
    hit1 = hit2 = hit3 = False
    targets = [(tp1, w1), (tp2, w2), (tp3, w3)]
    for j in range(j0, jend):
        if up:
            # stop on remaining position first (gap-realistic, worse fill)
            if remaining > 0 and lo[j] <= cur_stop:
                fill = min(cur_stop, op[j])
                realized += remaining * (fill - entry) / entry
                remaining = 0.0
                break
            if not hit1 and hi[j] >= tp1:
                realized += w1 * (tp1 - entry) / entry
                remaining -= w1; hit1 = True; cur_stop = entry      # stop -> BE
            if not hit2 and hi[j] >= tp2:
                realized += w2 * (tp2 - entry) / entry
                remaining -= w2; hit2 = True
            if not hit3 and hi[j] >= tp3:
                realized += w3 * (tp3 - entry) / entry
                remaining -= w3; hit3 = True
                remaining = max(0.0, remaining); break
        else:
            if remaining > 0 and hi[j] >= cur_stop:
                fill = max(cur_stop, op[j])
                realized += remaining * (entry - fill) / entry
                remaining = 0.0
                break
            if not hit1 and lo[j] <= tp1:
                realized += w1 * (entry - tp1) / entry
                remaining -= w1; hit1 = True; cur_stop = entry
            if not hit2 and lo[j] <= tp2:
                realized += w2 * (entry - tp2) / entry
                remaining -= w2; hit2 = True
            if not hit3 and lo[j] <= tp3:
                realized += w3 * (entry - tp3) / entry
                remaining -= w3; hit3 = True
                remaining = max(0.0, remaining); break
    if remaining > 1e-9:
        ex = cl[jend - 1]
        r = (ex - entry) / entry if up else (entry - ex) / entry
        realized += remaining * r
    return realized


def _entries_for(df):
    """Honest wave3 LONG entries (next_open), with HTF compass gate."""
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
            if bias < 0:                       # with-trend only
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
            tp1 = entry + TP_MULTS[0] * w1
            tp2 = entry + TP_MULTS[1] * w1
            tp3 = entry + TP_MULTS[2] * w1
            risk = abs(entry - s.stop_px)
            if risk <= 0 or (tp2 - entry) / risk < 1.0:
                continue
            jend = min(len(df), eb + 1 + TIMEOUT)
            out.append({
                "ts": df["ts"].iloc[eb], "entry": entry, "stop": s.stop_px,
                "tp1": tp1, "tp2": tp2, "tp3": tp3, "eb": eb, "jend": jend,
                "hi": hi, "lo": lo, "op": op, "cl": cl,
            })
    return out


def main():
    rows = []
    for tk in CRYPTO:
        df = download_binance_ohlc(tk, INTERVAL, PERIOD, min_rows=120)
        if df is None:
            continue
        df = df.reset_index(drop=True)
        df["ts"] = pd.to_datetime(df.index, utc=True, errors="coerce") \
            if "ts" not in df.columns else df["ts"]
        # download_binance_ohlc returns a DatetimeIndex; rebuild ts from it
        df["ts"] = pd.to_datetime(
            download_binance_ohlc(tk, INTERVAL, PERIOD, min_rows=120).index,
            utc=True, errors="coerce")
        for e in _entries_for(df):
            rows.append(e)

    if not rows:
        print("No entries.")
        return

    # OOS split: chronological 70/30 on entry ts (mirror LUT methodology).
    ts = pd.to_datetime([r["ts"] for r in rows], utc=True)
    order = np.argsort(ts.values)
    rows = [rows[i] for i in order]
    ts = ts[order]
    cut = ts[int(len(rows) * 0.70)]
    oos = [r for r, t in zip(rows, ts) if t > cut]

    def measure(sample, label):
        n = len(sample)
        r1 = r2 = r3 = 0
        n_stop = n_tp2 = n_timeout = 0
        mfes = []
        single_rets, scaled = [], {k: [] for k in WEIGHT_SCHEMES}
        for r in sample:
            a1, a2, a3, stopped = _reach_map(r["hi"], r["lo"], r["eb"] + 1, r["jend"],
                                       r["stop"], r["tp1"], r["tp2"], r["tp3"], True)
            r1 += a1; r2 += a2; r3 += a3
            # exit-reason breakdown for the single-target (TP2) sim
            hi, lo, op, cl = r["hi"], r["lo"], r["op"], r["cl"]
            reason = "timeout"
            mfe = 0.0
            for j in range(r["eb"] + 1, r["jend"]):
                mfe = max(mfe, (hi[j] - r["entry"]) / r["entry"])
                if lo[j] <= r["stop"]:
                    reason = "stop"; break
                if hi[j] >= r["tp2"]:
                    reason = "tp2"; break
            mfes.append(mfe)
            n_stop += reason == "stop"; n_tp2 += reason == "tp2"
            n_timeout += reason == "timeout"
            sr = _sim_single(r["hi"], r["lo"], r["op"], r["cl"], r["eb"] + 1,
                             r["jend"], r["entry"], r["stop"], r["tp2"], True)
            single_rets.append(sr - COST_RT)
            for name, (w1, w2, w3) in WEIGHT_SCHEMES.items():
                g = _sim_scaled(r["hi"], r["lo"], r["op"], r["cl"], r["eb"] + 1,
                                r["jend"], r["entry"], r["stop"],
                                r["tp1"], r["tp2"], r["tp3"], w1, w2, w3, True)
                scaled[name].append(g - COST_RT)
        print(f"\n=== {label}: n={n} ===")
        print(f"P(reach TP1=1.0xW1)   = {r1/n*100:5.1f}%")
        print(f"P(reach TP2=1.618xW1) = {r2/n*100:5.1f}%")
        print(f"P(reach TP3=2.618xW1) = {r3/n*100:5.1f}%")
        print(f"exit reason: stop={n_stop/n*100:.0f}%  tp2={n_tp2/n*100:.0f}%  "
              f"timeout={n_timeout/n*100:.0f}%   median MFE={np.median(mfes)*100:.1f}%")
        print(f"\n{'scheme':14}{'net EV%':>9}{'WR%':>7}{'vs single':>11}")
        base = np.mean(single_rets) * 100
        for name in WEIGHT_SCHEMES:
            arr = np.array(scaled[name])
            ev = arr.mean() * 100
            wr = (arr > 0).mean() * 100
            delta = ev - base
            tag = "  <-- current" if name == "single_TP2" else ""
            print(f"{name:14}{ev:>8.2f}%{wr:>6.0f}%{delta:>+10.2f}pp{tag}")
        return base

    measure(rows, "ALL (in+out of sample)")
    measure(oos, "OOS (test 30%)")


if __name__ == "__main__":
    main()
