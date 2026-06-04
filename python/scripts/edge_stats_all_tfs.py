"""Edge stats on all-TF dataset: compare flat/DC fade across 1w/4h/30m/15m/1h/1d."""
from __future__ import annotations
import sys, os, warnings
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PARQUET = os.path.join(REPO, "python", "data", "figures_all_tfs.parquet")
REPORT  = os.path.join(REPO, "docs", "validation", "sprint6-all-tfs.md")
OUT_DIR = os.path.join(REPO, "docs", "validation", "screenshots", "sprint6")

df = pd.read_parquet(PARQUET)
print(f"Total: {len(df)} figures")
print(df.groupby(["interval","fig_type"]).size().unstack(fill_value=0))


def t_test(s):
    s = s.dropna()
    if len(s) < 10: return np.nan, np.nan
    return stats.ttest_1samp(s, 0)

def row_stats(s, label):
    s = s.dropna()
    if len(s) < 5: return None
    t, p = t_test(s)
    return {"group": label, "n": len(s),
            "hit": (s>0).mean()*100, "mean": s.mean()*100,
            "sharpe": s.mean()/s.std() if s.std()>0 else np.nan,
            "t": t, "p": p}


lines = ["# Edge по всем таймфреймам (1w / 4h / 30m / 15m + 1h / 1d)",
         "",
         f"**Дата:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}",
         f"**Датасет:** {len(df)} фигур, {df['ticker'].nunique()} тикеров",
         "",
         "## Распределение фигур по ТФ",
         ""]

pivot = df.groupby(["interval","fig_type"]).size().unstack(fill_value=0)
lines.append(pivot.to_markdown())
lines.append("")

# Strategy: Flat+DC fade signed_ret_20
for ft in ["flat","double_corr"]:
    lines += [f"## {ft} — fade — signed_ret по таймфреймам (h=20)", "",
              "| interval | n | hit% | mean% | Sharpe | p |",
              "|---|---|---|---|---|---|"]
    sub = df[df["fig_type"]==ft]
    for itv in ["15m","30m","4h","1h","1d","1w"]:
        s = sub[sub["interval"]==itv]["signed_ret_20"].dropna()
        if len(s) < 10: continue
        r = row_stats(s, itv)
        if r:
            lines.append(f"| {itv} | {r['n']} | {r['hit']:.1f}% | "
                         f"{r['mean']:.2f}% | {r['sharpe']:.3f} | {r['p']:.4f} |")
    lines.append("")

# All TF combined heat-map: Sharpe per (fig_type × interval × horizon)
lines += ["## Heatmap Sharpe: fig_type × interval (h=20, fade)", ""]
rows_heat = []
for ft in ["flat","double_corr","impulse","triangle"]:
    for itv in ["15m","30m","4h","1h","1d","1w"]:
        s = df[(df["fig_type"]==ft) & (df["interval"]==itv)]["signed_ret_20"].dropna()
        if len(s) < 15: continue
        sh = s.mean()/s.std() if s.std()>0 else np.nan
        rows_heat.append({"fig_type":ft,"interval":itv,"n":len(s),"sharpe":sh,"hit":(s>0).mean()*100})
heat = pd.DataFrame(rows_heat)
if not heat.empty:
    pivot_sh = heat.pivot_table(index="fig_type", columns="interval", values="sharpe")
    lines.append(pivot_sh.round(2).to_markdown())
    lines.append("")
    pivot_hit = heat.pivot_table(index="fig_type", columns="interval", values="hit")
    lines += ["### Hit-rate % heatmap", ""]
    lines.append(pivot_hit.round(1).to_markdown())
    lines.append("")

# Focus: flat+DC best TFs for backtest
lines += ["## Flat+DC: топ комбинации по Sharpe (h=20, n≥20)", "",
          "| fig_type | interval | n | hit% | mean% | Sharpe | p |",
          "|---|---|---|---|---|---|---|"]
rows_best = []
for ft in ["flat","double_corr"]:
    for itv in ["15m","30m","4h","1h","1d","1w"]:
        s = df[(df["fig_type"]==ft) & (df["interval"]==itv)]["signed_ret_20"].dropna()
        if len(s) < 20: continue
        t, p = t_test(s)
        sh = s.mean()/s.std() if s.std()>0 else np.nan
        rows_best.append({"fig_type":ft,"interval":itv,"n":len(s),
                          "hit":(s>0).mean()*100,"mean":s.mean()*100,"sharpe":sh,"p":p})
rows_best.sort(key=lambda x: -x["sharpe"])
for r in rows_best:
    lines.append(f"| {r['fig_type']} | {r['interval']} | {r['n']} | "
                 f"{r['hit']:.1f}% | {r['mean']:.2f}% | {r['sharpe']:.3f} | {r['p']:.4f} |")
lines.append("")

with open(REPORT, "w") as f:
    f.write("\n".join(lines))
print(f"Report: {REPORT}")
