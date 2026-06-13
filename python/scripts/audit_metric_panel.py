"""Neely audit — full statistical metric panel across all validated setups.

For each (asset_class, interval, fig_type, side) it computes the panel that
actually decides whether a setup deserves capital:
  n, WR, net EV/trade, realized Reward:Risk, Profit Factor, per-trade Sharpe,
  t-statistic, breakeven-WR margin, and OOS EV (70/30 split).

Verdict rule (the metrics that matter, not winrate):
  CAPITAL  — net EV>0 AND t-stat>2 AND Profit Factor>1.5 AND OOS EV>0
  MARGINAL — net EV>0 but fails significance/robustness
  REJECT   — net EV<=0

Sources:
  wave3            -> live detection (honest next_open fill, gap stop, cost)
  flat / flat_htf  -> historical signal grid per-trade net_ret (contract slice)

Run: python scripts/audit_metric_panel.py
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

COST = {"crypto": 2 * 0.0010 + 0.0005, "stock": 2 * 0.0001 + 0.0002}
TIMEOUT = {"1h": 24, "4h": 18, "1d": 12}
MAXW1 = {"1h": 0.15, "4h": 0.30, "1d": 0.50}
COMPASS = {"1h": "1D", "4h": "1D", "1d": "1W"}
CRYPTO = ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "ADA-USD", "AVAX-USD",
          "LINK-USD", "DOT-USD", "NEAR-USD", "INJ-USD", "AAVE-USD", "ATOM-USD",
          "LTC-USD", "XLM-USD", "OP-USD", "HBAR-USD", "FIL-USD", "TRX-USD"]
CRYPTO_TF = [("1h", "365d"), ("4h", "730d"), ("1d", "1500d")]
STOCK_CACHE = ROOT / "python" / "data" / "ohlc_cache" / "tiingo"
GRID = ROOT / "python" / "data"


def panel(rets: np.ndarray, oos: np.ndarray | None = None) -> dict:
    a = np.asarray(rets, dtype=float)
    n = len(a)
    if n < 5:
        return {}
    wins, losses = a[a > 0], a[a <= 0]
    wr = len(wins) / n
    ev = a.mean()
    avg_w = wins.mean() if len(wins) else 0.0
    avg_l = losses.mean() if len(losses) else 0.0
    rr = abs(avg_w / avg_l) if avg_l != 0 else 0.0
    pf = wins.sum() / abs(losses.sum()) if losses.sum() != 0 else float("inf")
    std = a.std(ddof=1) if n > 1 else 0.0
    tstat = ev / std * np.sqrt(n) if std > 0 else 0.0
    be_wr = 1 / (1 + rr) if rr > 0 else 1.0
    oos_ev = float(np.mean(oos)) if oos is not None and len(oos) else float("nan")
    return {"n": n, "wr": wr, "ev": ev, "rr": rr, "pf": pf, "tstat": tstat,
            "be_wr": be_wr, "wr_margin": wr - be_wr, "oos_ev": oos_ev}


def _wave3_rets(df, interval, asset):
    hi, lo, op, cl = (df["high"].values, df["low"].values,
                      df["open"].values, df["close"].values)
    piv = detect_monowaves(df, atr_mult=2.5)
    classify_pivots(piv)
    try:
        compass = structural_trend_series(
            df.set_index(pd.to_datetime(df["ts"], utc=True)), COMPASS[interval]).values
    except Exception:
        compass = None
    ps = sorted((p for p in piv if p.confirmation_idx >= 0),
                key=lambda p: p.confirmation_idx)
    known, pp, seen = [], 0, set()
    out = {"long": [], "short": []}        # (ret, ts)
    cost = COST[asset]; tmo = TIMEOUT[interval]; frac = MAXW1[interval]
    for i in range(60, len(df) - 1):
        while pp < len(ps) and ps[pp].confirmation_idx <= i:
            known.append(ps[pp]); pp += 1
        if len(known) < 3:
            continue
        bias = int(compass[i]) if compass is not None and i < len(compass) else 0
        for s in detect_wave3_setups(known, float(cl[i]), i, max_w1_frac=frac):
            if not (s.triggered and s.struct_ok and s.rr1 >= 1.0):
                continue
            up = s.side == "long"
            if (bias > 0 and not up) or (bias < 0 and up):
                continue
            k = (round(s.entry_px, 4), round(s.stop_px, 4))
            if k in seen:
                continue
            seen.add(k); eb = i + 1; e = float(op[eb])
            if e <= 0:
                continue
            w1 = abs(s.w1_end - s.w1_start)
            tp = e + (1 if up else -1) * TP_MULTS[1] * w1
            risk = abs(e - s.stop_px)
            if risk <= 0 or abs(tp - e) / risk < 1.0:
                continue
            jend = min(len(cl), eb + 1 + tmo)
            r = None
            for j in range(eb + 1, jend):
                if up:
                    if lo[j] <= s.stop_px: r = (min(s.stop_px, op[j]) - e) / e; break
                    if hi[j] >= tp: r = (tp - e) / e; break
                else:
                    if hi[j] >= s.stop_px: r = (e - max(s.stop_px, op[j])) / e; break
                    if lo[j] <= tp: r = (e - tp) / e; break
            if r is None:
                ex = cl[jend - 1]; r = (ex - e) / e if up else (e - ex) / e
            out[s.side].append((r - cost, df["ts"].iloc[eb]))
    return out


def collect_wave3():
    groups: dict = {}
    # stocks 1d
    import glob
    for f in sorted(glob.glob(str(STOCK_CACHE / "*_1d_5y.parquet"))):
        df = pd.read_parquet(f)
        if "date" in df.columns: df = df.set_index("date")
        df.columns = [str(c).lower() for c in df.columns]
        if not {"open", "high", "low", "close"}.issubset(df.columns): continue
        df = df.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)
        df["ts"] = pd.to_datetime(pd.read_parquet(f).index if "date" not in pd.read_parquet(f).columns
                                  else pd.read_parquet(f)["date"], utc=True, errors="coerce")
        if len(df) < 120: continue
        r = _wave3_rets(df, "1d", "stock")
        for side in ("long", "short"):
            groups.setdefault(("stock", "1d", "wave3", side), []).extend(r[side])
    # crypto multi-TF
    for tk in CRYPTO:
        for interval, period in CRYPTO_TF:
            df = download_binance_ohlc(tk, interval, period, min_rows=120)
            if df is None: continue
            df = df.reset_index(drop=False)
            df["ts"] = pd.to_datetime(df.iloc[:, 0], utc=True, errors="coerce")
            r = _wave3_rets(df, interval, "crypto")
            for side in ("long", "short"):
                groups.setdefault(("crypto", interval, "wave3", side), []).extend(r[side])
    return groups


def collect_grid():
    """flat (mtf none) + flat_htf (mtf aligned) per-trade from the grid."""
    ALIGNED = "long_only_htf_up_short_only_htf_down"
    frames = []
    for n, ac in [("historical_signal_grid_trades.parquet", "stock"),
                  ("historical_signal_grid_crypto_trades.parquet", "crypto")]:
        p = GRID / n
        if p.exists():
            d = pd.read_parquet(p)
            if "asset_class" not in d.columns: d["asset_class"] = ac
            frames.append(d)
    if not frames:
        return {}
    g = pd.concat(frames, ignore_index=True)
    base = g[(g.fig_type == "flat")
             & (g.entry_variant.isin(["next_open", "next_bar_open"]))
             & (g.tp_mult == 1.618) & (g.sl_mult == 1.0) & (g.late_limit == 999.0)]
    groups: dict = {}
    for fig, mtf in [("flat", "none"), ("flat_htf", ALIGNED)]:
        s = base[base.mtf_policy == mtf]
        for (ac, iv, side), sub in s.groupby(["asset_class", "interval", "side"]):
            sub = sub.copy()
            sub["entry_ts"] = pd.to_datetime(sub["entry_ts"], utc=True, errors="coerce")
            rows = [(float(nr), ts) for nr, ts in zip(sub["net_ret"], sub["entry_ts"])
                    if pd.notna(nr)]
            if rows:
                groups[(ac, iv, fig, side)] = rows
    return groups


def main():
    groups = {}
    groups.update(collect_wave3())
    groups.update(collect_grid())

    panels = []
    for key, rows in groups.items():
        if len(rows) < 20:
            continue
        rows = sorted(rows, key=lambda x: pd.Timestamp(x[1]) if pd.notna(x[1]) else pd.Timestamp(0))
        rets = np.array([r for r, _ in rows])
        cut = int(len(rets) * 0.70)
        oos = rets[cut:]
        p = panel(rets, oos)
        if not p:
            continue
        p["key"] = "/".join(map(str, key))
        # verdict
        if p["ev"] <= 0:
            p["verdict"] = "REJECT"
        elif p["tstat"] > 2 and p["pf"] > 1.5 and p["oos_ev"] > 0:
            p["verdict"] = "CAPITAL"
        else:
            p["verdict"] = "MARGINAL"
        panels.append(p)

    panels.sort(key=lambda p: -p["tstat"])
    print(f"\n{'setup':34}{'n':>5}{'WR%':>6}{'EV%':>7}{'R:R':>6}{'PF':>6}"
          f"{'t':>6}{'WRmrg':>7}{'OOS%':>7}  verdict")
    print("-" * 100)
    for p in panels:
        print(f"{p['key']:34}{p['n']:>5}{p['wr']*100:>5.0f}%{p['ev']*100:>6.2f}%"
              f"{p['rr']:>6.2f}{p['pf']:>6.2f}{p['tstat']:>6.2f}"
              f"{p['wr_margin']*100:>+6.0f}%{p['oos_ev']*100:>6.2f}%  {p['verdict']}")
    caps = [p for p in panels if p["verdict"] == "CAPITAL"]
    print(f"\nCAPITAL-worthy (EV>0, t>2, PF>1.5, OOS>0): {len(caps)} / {len(panels)}")
    for p in sorted(caps, key=lambda x: -x["ev"]):
        print(f"  {p['key']:34} EV {p['ev']*100:+.2f}%/трейд  t={p['tstat']:.1f}  PF={p['pf']:.2f}  n={p['n']}")


if __name__ == "__main__":
    main()
