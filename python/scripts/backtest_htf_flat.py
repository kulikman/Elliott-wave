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
    s = g[(g.fig_type == "flat") & (g.entry_variant == "confirm_close")
          & (g.tp_mult == 1.618) & (g.sl_mult == 1.0) & (g.late_limit == 999.0)
          & (g.mtf_policy == mtf)].copy()
    s["entry_ts"] = pd.to_datetime(s["entry_ts"], utc=True, errors="coerce")
    return s.dropna(subset=["entry_ts"]).sort_values("entry_ts")


def _grp(frame: pd.DataFrame, fig_label: str) -> pd.DataFrame:
    f = frame.assign(fig_type=fig_label)
    return (f.groupby(KEYS)
            .agg(trades=("win", "size"), winrate=("win", "mean"),
                 expectancy=("net_ret", "mean")).reset_index())


def main() -> None:
    g = _load()
    if g.empty:
        print("no grid data")
        return
    aligned = _slice(g, ALIGNED)
    plain = _slice(g, "none")
    cut = aligned["entry_ts"].quantile(0.70)

    g_tr = _grp(aligned[aligned.entry_ts <= cut], "flat_htf")
    g_te = _grp(aligned[aligned.entry_ts > cut], "flat_htf")
    # plain-flat OOS EV for comparison (same split)
    pcut = plain["entry_ts"].quantile(0.70)
    p_te = _grp(plain[plain.entry_ts > pcut], "flat")

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
    print(f"split @ {str(cut)[:10]} | HTF-aligned flat setups stable OOS: {len(lut)}")
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
