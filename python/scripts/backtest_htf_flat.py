"""Backtest HTF-aligned LTF flat entries (EPIC G) with OOS + stability.

The idea: when the higher TF trend is up, only take LTF flat-fade LONGs (and
mirror for down) — enter the LTF pullback in the direction the bigger wave
resumes. The historical signal grid already tags every trade with htf_bias and
an mtf_policy, so the aligned subset is the validated proxy for this idea.

Reads the grid's contract slice (confirm_close, TP 1.618, SL 1.0, late off)
with mtf_policy=long_only_htf_up_short_only_htf_down, does a 70/30 chronological
split, keeps only (asset, interval, side) setups positive in BOTH periods, and
writes OOS metrics to ewb_htf_flat_backtest_grouped.parquet under fig_type
"flat_htf". The gate merges it; only setups that BEAT the plain-flat OOS EV are
worth the extra HTF machinery (reported below).

Run: python scripts/backtest_htf_flat.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "brain-output" / "backtests" / "ewb_htf_flat_backtest_grouped.parquet"
ALIGNED = "long_only_htf_up_short_only_htf_down"
KEYS = ["asset_class", "interval", "fig_type", "side"]


def _load() -> pd.DataFrame:
    fr = []
    for n, ac in [("historical_signal_grid_trades.parquet", "stock"),
                  ("historical_signal_grid_crypto_trades.parquet", "crypto")]:
        p = ROOT / "python" / "data" / n
        if p.exists():
            d = pd.read_parquet(p)
            d["asset_class"] = ac
            fr.append(d)
    return pd.concat(fr, ignore_index=True) if fr else pd.DataFrame()


def _slice(g: pd.DataFrame, mtf: str) -> pd.DataFrame:
    # next_open execution: stock grid labels it "next_open", crypto "next_bar_open".
    # Only 1h/4h: the live emitter (_emit_htf_flat, _HTF_RULE={1h:4h,4h:1D}) makes
    # flat_htf signals only on those LTFs, so other intervals would be dead LUT
    # rows that never match a signal. This is exactly the idea — enter on 1h/4h.
    s = g[(g.fig_type == "flat") & (g.entry_variant.isin(["next_open", "next_bar_open"]))
          & (g.interval.isin(["1h", "4h"]))
          & (g.tp_mult == 1.618) & (g.sl_mult == 1.0) & (g.late_limit == 999.0)
          & (g.mtf_policy == mtf)].copy()
    s["entry_ts"] = pd.to_datetime(s["entry_ts"], utc=True, errors="coerce")
    return s.dropna(subset=["entry_ts"]).sort_values("entry_ts")


def _grp(frame: pd.DataFrame, fig_label: str) -> pd.DataFrame:
    f = frame.assign(fig_type=fig_label)
    return (f.groupby(KEYS)
            .agg(trades=("win", "size"), winrate=("win", "mean"),
                 expectancy=("net_ret", "mean")).reset_index())


def _per_setup_split(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """70/30 chronological split computed PER (asset, interval, side), not on a
    single global cutoff. A global cutoff is set by the high-frequency setups
    (stock/crypto 1h, 200-466 trades) and compresses the OOS window to a few
    months — which starves sparse 4h setups (~100 trades / 4y → ~4 in the test)
    and wrongly fails them on sample size. A per-setup cutoff gives each a
    proportional, still-recent OOS window; the stability filter (positive in
    BOTH the setup's own train and test) remains the overfitting guard."""
    tr_parts, te_parts = [], []
    for _, sub in frame.groupby(["asset_class", "interval", "side"]):
        sub = sub.sort_values("entry_ts")
        if len(sub) < 10:
            continue
        c = sub["entry_ts"].quantile(0.70)
        tr_parts.append(sub[sub.entry_ts <= c])
        te_parts.append(sub[sub.entry_ts > c])
    empty = frame.iloc[0:0]
    tr = pd.concat(tr_parts) if tr_parts else empty
    te = pd.concat(te_parts) if te_parts else empty
    return tr, te


def main() -> None:
    g = _load()
    if g.empty:
        print("no grid data")
        return
    aligned = _slice(g, ALIGNED)
    plain = _slice(g, "none")

    a_tr, a_te = _per_setup_split(aligned)
    g_tr = _grp(a_tr, "flat_htf")
    g_te = _grp(a_te, "flat_htf")
    # plain-flat OOS EV for comparison (same per-setup split)
    _, p_te_raw = _per_setup_split(plain)
    p_te = _grp(p_te_raw, "flat")

    m = g_te.merge(g_tr, on=KEYS, how="left", suffixes=("_oos", "_is"))
    stable = m[(m.expectancy_oos > 0) & (m.expectancy_is > 0)].copy()
    lut = (stable[KEYS + ["trades_oos", "winrate_oos", "expectancy_oos"]]
           .rename(columns={"trades_oos": "trades", "winrate_oos": "winrate",
                            "expectancy_oos": "expectancy"}))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    lut.to_parquet(OUT, index=False)

    # compare aligned vs plain OOS EV per (asset, interval, side)
    cmp = stable.merge(
        p_te.rename(columns={"expectancy": "plain_ev", "winrate": "plain_wr",
                             "trades": "plain_n"}),
        left_on=["asset_class", "interval", "side"],
        right_on=["asset_class", "interval", "side"], how="left")
    print(f"per-setup 70/30 split | HTF-aligned flat setups stable OOS: {len(lut)}")
    print(f"{'asset/tf/side':<18}{'HTF_WR%':>8}{'HTF_EV%':>8}{'n':>5}{'plain_EV%':>11}{'beats?':>8}")
    for _, r in cmp.sort_values("expectancy_oos", ascending=False).iterrows():
        pe = r.get("plain_ev")
        beats = "yes" if pd.notna(pe) and r["expectancy_oos"] > pe else "no"
        print(f"{r.asset_class+'/'+r.interval+'/'+r.side:<18}"
              f"{r.winrate_oos*100:>7.0f}{r.expectancy_oos*100:>8.2f}{int(r.trades_oos):>5}"
              f"{(pe*100 if pd.notna(pe) else float('nan')):>10.2f}{beats:>8}")
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
