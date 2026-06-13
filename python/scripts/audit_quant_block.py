"""Quant block (1)+(2)+(3): significance + multiple-testing + correlation + Kelly.

Completes the strategy audit with the rigour that actually protects EV:

(1) SIGNIFICANCE across ALL setups incl. core — per-trade panel (EV, t-stat, PF)
    over wave3 (live detection), flat/flat_htf (grid), core_* (AB-test B group).
(2) MULTIPLE-TESTING correction — we ran ~N setups and kept the best, so some
    "significant" results are luck. Apply Benjamini-Hochberg FDR (q=0.05) on the
    p-values AND the expected-max-t under the null (deflated threshold). A setup
    is ROBUST only if it clears both.
(3) CORRELATION + KELLY — monthly PnL correlation across robust setups (real
    diversification, not per-setup EV) and fractional-Kelly sizing (growth-
    optimal bankroll fraction) to replace the flat $100.

Honest fill throughout (next_open, cost). Read-only. Run:
    python scripts/audit_quant_block.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))
sys.path.insert(0, str(ROOT / "python" / "scripts"))

from audit_metric_panel import collect_wave3, collect_grid, panel  # noqa: E402

SCAN_INTERVALS = {"1h", "4h", "1d", "1w"}
CORE_TRADES = ROOT / "python" / "data" / "neely_core_ab_backtest_trades.parquet"
MIN_N = 30
FDR_Q = 0.05


def collect_core() -> dict:
    """core_* setups (AB-test B group) per-trade net_ret + entry_ts."""
    if not CORE_TRADES.exists():
        return {}
    d = pd.read_parquet(CORE_TRADES)
    d = d[(d["ab_group"] == "B") & (d["interval"].isin(SCAN_INTERVALS))]
    d = d.dropna(subset=["net_ret", "entry_ts"])
    d["entry_ts"] = pd.to_datetime(d["entry_ts"], utc=True, errors="coerce")
    groups: dict = {}
    for (ac, iv, setup, side), g in d.groupby(["asset_class", "interval", "setup", "side"]):
        rows = [(float(r), t) for r, t in zip(g["net_ret"], g["entry_ts"]) if pd.notna(t)]
        if rows:
            groups[(ac, iv, setup, side)] = rows
    return groups


def _t_pvalue(t: float, n: int) -> float:
    """Two-sided p-value for a t-stat with n-1 df. Normal approx (n large)."""
    if n < 2:
        return 1.0
    z = abs(t)
    return math.erfc(z / math.sqrt(2.0))          # 2*(1-Phi(z))


def _expected_max_t(N: int) -> float:
    """Expected maximum of N iid standard normals — the t a spurious 'best'
    setup reaches by chance when N are screened (multiple-testing threshold)."""
    if N < 2:
        return 0.0
    a = math.sqrt(2 * math.log(N))
    return a - (math.log(math.log(N)) + math.log(4 * math.pi)) / (2 * a)


def _monthly_pnl(rows) -> pd.Series:
    s = pd.Series([r for r, _ in rows],
                  index=pd.to_datetime([t for _, t in rows], utc=True))
    return s.groupby(s.index.to_period("M")).sum()


def main():
    groups = {}
    groups.update(collect_wave3())
    groups.update(collect_grid())
    groups.update(collect_core())

    # ── (1) significance panel per setup ──
    recs = []
    for key, rows in groups.items():
        if len(rows) < MIN_N:
            continue
        rows = sorted(rows, key=lambda x: x[1])
        rets = np.array([r for r, _ in rows])
        cut = int(len(rets) * 0.70)
        p = panel(rets, rets[cut:])
        if not p:
            continue
        pval = _t_pvalue(p["tstat"], p["n"])
        recs.append({"key": "/".join(map(str, key)), "rows": rows,
                     "n": p["n"], "wr": p["wr"], "ev": p["ev"], "pf": p["pf"],
                     "tstat": p["tstat"], "oos_ev": p["oos_ev"], "pval": pval})

    N = len(recs)
    t_thresh = _expected_max_t(N)

    # ── (2) Benjamini-Hochberg FDR ──
    recs.sort(key=lambda r: r["pval"])
    bh_cut = 0
    for i, r in enumerate(recs, 1):
        if r["pval"] <= (i / N) * FDR_Q:
            bh_cut = i
    for i, r in enumerate(recs, 1):
        r["bh_pass"] = i <= bh_cut
        r["deflated_pass"] = r["tstat"] > t_thresh
        r["robust"] = r["bh_pass"] and r["deflated_pass"] and r["oos_ev"] > 0 and r["ev"] > 0

    print(f"=== (1)+(2) SIGNIFICANCE under multiple testing (N={N} setups screened) ===")
    print(f"BH-FDR q={FDR_Q}: reject null for {bh_cut} smallest p-values")
    print(f"Deflated t-threshold (E[max t] under null) = {t_thresh:.2f}  "
          f"→ t must exceed this to beat 'best-by-chance'\n")
    print(f"{'setup':40}{'n':>5}{'EV%':>7}{'PF':>6}{'t':>6}{'p':>9}{'BH':>4}{'defl':>6}{'ROBUST':>8}")
    print("-" * 96)
    for r in sorted(recs, key=lambda x: -x["tstat"]):
        print(f"{r['key']:40}{r['n']:>5}{r['ev']*100:>6.2f}%{r['pf']:>6.2f}{r['tstat']:>6.2f}"
              f"{r['pval']:>9.1e}{'Y' if r['bh_pass'] else '·':>4}"
              f"{'Y' if r['deflated_pass'] else '·':>6}{'ROBUST' if r['robust'] else '':>8}")

    robust = [r for r in recs if r["robust"]]
    print(f"\nROBUST setups (BH-FDR + deflated-t + OOS>0): {len(robust)} / {N}")

    if len(robust) < 2:
        print("Too few robust setups for correlation/Kelly.")
        return

    # ── (3) correlation matrix (monthly PnL) ──
    pnl = {r["key"]: _monthly_pnl(r["rows"]) for r in robust}
    M = pd.DataFrame(pnl).sort_index()
    M = M.fillna(0.0)                       # a flat month = no position = 0 PnL
    C = M.corr()
    iu = np.triu_indices(len(C), 1)
    avg_corr = float(C.values[iu].mean())
    print(f"\n=== (3) CORRELATION (monthly PnL, {len(robust)} robust setups, "
          f"{len(M)} months) ===")
    print(f"avg pairwise correlation: {avg_corr:.2f}  "
          f"(low = real diversification)")
    # most diversifying pairs (lowest corr)
    pairs = sorted(((C.iloc[i, j], C.index[i], C.columns[j]) for i, j in zip(*iu)),
                   key=lambda x: x[0])
    print("most-diversifying pairs (lowest corr):")
    for c, a, b in pairs[:5]:
        print(f"  {c:+.2f}  {a}  ⟂  {b}")

    # ── (3) fractional Kelly sizing ──
    # Per-trade growth-optimal leverage f* = mean/variance (independent proxy);
    # half-Kelly for safety. Relative allocation ∝ f*.
    print(f"\n=== KELLY SIZING (independent half-Kelly, relative allocation) ===")
    kel = []
    for r in robust:
        rets = np.array([x for x, _ in r["rows"]])
        var = rets.var(ddof=1)
        f_full = r["ev"] / var if var > 0 else 0.0
        kel.append((r["key"], r["ev"], var, f_full))
    tot = sum(max(0.0, 0.5 * f) for _, _, _, f in kel) or 1.0
    print(f"{'setup':40}{'EV%':>7}{'σ%':>7}{'½Kelly':>9}{'alloc%':>8}")
    for key, ev, var, f in sorted(kel, key=lambda x: -x[3]):
        half = 0.5 * f
        alloc = max(0.0, half) / tot * 100
        print(f"{key:40}{ev*100:>6.2f}%{math.sqrt(var)*100:>6.1f}%{half:>9.2f}{alloc:>7.1f}%")
    print("\nNote: allocation ∝ half-Kelly leverage (EV/variance). Correlation-")
    print("adjusted Kelly (Σ⁻¹μ) would tilt further toward the low-corr pairs above.")

    # ── persist a sizing LUT for the live trader ──
    # Restrict to LIVE-SCANNED intervals (1h/4h/1d/1w) — 30m/15m are not traded.
    # kelly_mult = clip( (EV/var) / median(EV/var), 0.25, 3.0 ): a growth-optimal
    # position multiplier centred at 1.0 (typical setup), capped for fat-tail
    # safety. Variance penalises high-vol setups (the flagship gets sized DOWN).
    tradeable = [(key, ev, var, ev / var) for key, ev, var, f in kel
                 if key.split("/")[1] in SCAN_INTERVALS and var > 0]
    if tradeable:
        ref = float(np.median([s for *_, s in tradeable])) or 1.0
        rows = []
        for key, ev, var, score in tradeable:
            ac, iv, fig, side = key.split("/")
            mult = float(np.clip(score / ref, 0.25, 3.0))
            rows.append({"asset_class": ac, "interval": iv, "fig_type": fig,
                         "side": side, "ev": float(ev), "variance": float(var),
                         "kelly_mult": round(mult, 3)})
        out = ROOT / "brain-output" / "backtests" / "ewb_kelly_sizing.parquet"
        pd.DataFrame(rows).to_parquet(out, index=False)
        print(f"\nWrote {out.name}: {len(rows)} tradeable-setup Kelly multipliers "
              f"(ref EV/var={ref:.2f}, mult∈[0.25,3.0])")


if __name__ == "__main__":
    main()
