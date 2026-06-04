"""Sprint 4 extended — edge stats on wide dataset (10k+ figures)."""
from __future__ import annotations
import sys, os, warnings
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PARQUET = os.path.join(REPO, "python", "data", "figures_wide.parquet")
REPORT  = os.path.join(REPO, "docs", "validation", "sprint4-edge-wide.md")
OUT_DIR = os.path.join(REPO, "docs", "validation", "screenshots", "sprint4")
os.makedirs(OUT_DIR, exist_ok=True)

HORIZONS = [5, 10, 20, 50, 100]


def t_test(s: pd.Series):
    s = s.dropna()
    if len(s) < 10: return np.nan, np.nan
    t, p = stats.ttest_1samp(s, 0)
    return t, p


def stats_row(s: pd.Series, label: str) -> dict:
    s = s.dropna()
    if len(s) == 0:
        return None
    t, p = t_test(s)
    return {
        "group": label,
        "n": len(s),
        "hit_rate": (s > 0).mean(),
        "mean_ret": s.mean(),
        "std_ret": s.std(),
        "sharpe": s.mean() / s.std() if s.std() > 0 else np.nan,
        "t_stat": t,
        "p_value": p,
    }


def grouped(df, gby, signal_col, horizon, min_n=20):
    rows = []
    for keys, grp in df.groupby(gby):
        s = grp[f"{signal_col}_{horizon}"].dropna()
        if len(s) < min_n: continue
        r = stats_row(s, str(keys))
        if r is None: continue
        if not isinstance(keys, tuple): keys = (keys,)
        col_names = gby if isinstance(gby, list) else [gby]
        for k, v in zip(col_names, keys):
            r[k] = v
        rows.append(r)
    cols_keep = (gby if isinstance(gby, list) else [gby]) + ["n","hit_rate","mean_ret","sharpe","t_stat","p_value"]
    return pd.DataFrame(rows)[cols_keep] if rows else pd.DataFrame()


def fmt(df, cols_pct=None, cols_round=None):
    df = df.copy()
    cols_pct = cols_pct or []
    cols_round = cols_round or []
    for c in cols_pct:
        if c in df.columns:
            df[c] = (df[c]*100).round(2).astype(str) + "%"
    for c in cols_round:
        if c in df.columns:
            df[c] = df[c].round(3)
    return df.to_markdown(index=False)


def main():
    df = pd.read_parquet(PARQUET)
    print(f"Loaded: {len(df)} figures")
    print(f"By type:\n{df['fig_type'].value_counts()}")
    print(f"By interval:\n{df['interval'].value_counts()}")

    out = ["# Спринт 4 — Wide Edge Discovery",
           "",
           f"**Дата:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}",
           f"**Датасет:** {len(df)} фигур, {df['ticker'].nunique()} тикеров, ТФ: {sorted(df['interval'].unique())}",
           "",
           f"**Распределение по типам:**",
           ""]
    for t, c in df["fig_type"].value_counts().items():
        out.append(f"- {t}: {c}")
    out.append("")

    # ─── H0: baseline all ────────────────
    out += ["## H0 — Baseline (без фильтра)", "",
            "| Горизонт | n | hit_rate | mean_ret | Sharpe | p-value |",
            "|---|---|---|---|---|---|"]
    for h in HORIZONS:
        r = stats_row(df[f"signed_ret_{h}"], "all")
        if r:
            out.append(f"| {h} | {r['n']} | {r['hit_rate']*100:.1f}% | {r['mean_ret']*100:.2f}% | "
                       f"{r['sharpe']:.3f} | {r['p_value']:.4f} |")
    out += [""]

    # ─── H1: by fig_type per horizon ────────────────
    out += ["## H1 — По типу фигуры × горизонту (без HTF фильтра)", ""]
    for h in HORIZONS:
        out += [f"### Горизонт {h} баров", ""]
        t = grouped(df, "fig_type", "signed_ret", h, min_n=50)
        if not t.empty:
            out.append(fmt(t.sort_values("hit_rate", ascending=False),
                          cols_pct=["hit_rate","mean_ret"], cols_round=["sharpe","t_stat","p_value"]))
        out += [""]

    # ─── H2: HTF filter — main test ────────────────
    out += ["## H2 — HTF bias фильтр (главный тест)", ""]
    for h in [10, 20, 50]:
        out += [f"### Горизонт {h} баров", ""]
        t = grouped(df, ["fig_type","with_htf"], "signed_ret", h, min_n=30)
        if not t.empty:
            out.append(fmt(t.sort_values(["fig_type","with_htf"]),
                          cols_pct=["hit_rate","mean_ret"], cols_round=["sharpe","t_stat","p_value"]))
        out += [""]

    # ─── H3: per-interval ────────────────
    out += ["## H3 — Различия между таймфреймами", ""]
    t = grouped(df[df["with_htf"]==True], ["fig_type","interval"], "signed_ret", 20, min_n=30)
    if not t.empty:
        out.append("С HTF фильтром, h=20:")
        out.append("")
        out.append(fmt(t.sort_values(["fig_type","interval"]),
                       cols_pct=["hit_rate","mean_ret"], cols_round=["sharpe","t_stat","p_value"]))
    out += [""]

    # ─── H4: walk-forward ────────────────
    out += ["## H4 — Walk-forward (5 окон по времени)", ""]
    df["entry_ts"] = pd.to_datetime(df["entry_ts"], utc=True, errors='coerce')
    df_sorted = df.sort_values("entry_ts").dropna(subset=["entry_ts"])
    n = len(df_sorted)
    folds = [(i*n//5, (i+1)*n//5) for i in range(5)]
    fold_results = []
    for fold_i, (a, b) in enumerate(folds):
        sub = df_sorted.iloc[a:b]
        sub_htf = sub[sub["with_htf"]==True]
        for ft in ["impulse","triangle","flat"]:
            s = sub_htf[sub_htf["fig_type"]==ft]["signed_ret_20"].dropna()
            if len(s) < 20: continue
            fold_results.append({
                "fold": fold_i,
                "period": f"{sub.iloc[0]['entry_ts'].date()} → {sub.iloc[-1]['entry_ts'].date()}",
                "fig_type": ft,
                "n": len(s),
                "hit_rate": (s>0).mean(),
                "mean_ret": s.mean(),
                "p_value": t_test(s)[1],
            })
    fold_df = pd.DataFrame(fold_results)
    if not fold_df.empty:
        out.append(fmt(fold_df, cols_pct=["hit_rate","mean_ret"], cols_round=["p_value"]))
    out += [""]

    # ─── H5: amplitude / duration features ────────────────
    out += ["## H5 — Влияние размера фигуры", ""]
    # Quartiles of amp_pct
    df["amp_q"] = pd.qcut(df["amp_pct"], 4, labels=["Q1_small","Q2","Q3","Q4_large"])
    htf_only = df[df["with_htf"]==True]
    t = grouped(htf_only, ["fig_type","amp_q"], "signed_ret", 20, min_n=20)
    if not t.empty:
        out.append("Edge по квартилям амплитуды (с HTF):")
        out.append("")
        out.append(fmt(t.sort_values(["fig_type","amp_q"]),
                       cols_pct=["hit_rate","mean_ret"], cols_round=["sharpe","t_stat","p_value"]))
    out += [""]

    # ─── Final verdict ────────────────
    out += ["## Финальный вердикт", ""]
    # Find best edge candidates
    best = []
    for h in HORIZONS:
        # with HTF filter only
        t = grouped(df[df["with_htf"]==True], "fig_type", "signed_ret", h, min_n=50)
        if t.empty: continue
        for _, row in t.iterrows():
            if row["p_value"] < 0.05 and row["hit_rate"] > 0.55:
                best.append({
                    "horizon": h,
                    "filter": "with_htf",
                    **row.to_dict()
                })
    if best:
        out += ["**Статистически значимый edge (p<0.05, hit>55%, с HTF фильтром):**", ""]
        out.append("| Гориз | fig_type | n | hit_rate | mean_ret | Sharpe | p |")
        out.append("|---|---|---|---|---|---|---|")
        for b in sorted(best, key=lambda x: -x["hit_rate"]):
            out.append(f"| {b['horizon']} | {b['fig_type']} | {int(b['n'])} | "
                       f"{b['hit_rate']*100:.1f}% | {b['mean_ret']*100:.2f}% | "
                       f"{b['sharpe']:.3f} | {b['p_value']:.4f} |")
        out += ["",
                "**Gate Спринта 4 пройден.** Edge подтверждён на n≥50, p<0.05, hit≥55%.",
                "Переход в Спринт 5 (baseline ML)."]
    else:
        out += ["**Edge не подтверждён на широкой выборке.** Сигнал из Sprint 4 (n=234) ",
                "был случайностью малой выборки. Пересмотр гипотез."]

    # Plots
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    for ax, h in zip(axes.flat, [5, 20, 50, 100]):
        s_with = df[df["with_htf"]==True][f"signed_ret_{h}"].dropna() * 100
        s_against = df[df["against_htf"]==True][f"signed_ret_{h}"].dropna() * 100
        ax.hist(s_with, bins=50, alpha=0.6, color="#22cc55", label=f"with_HTF n={len(s_with)}")
        ax.hist(s_against, bins=50, alpha=0.6, color="#cc3344", label=f"against_HTF n={len(s_against)}")
        ax.axvline(0, color="white", lw=1, ls="--")
        ax.set_title(f"signed_ret_{h}: with-HTF hit={(s_with>0).mean()*100:.1f}%, "
                     f"against-HTF hit={(s_against>0).mean()*100:.1f}%")
        ax.legend(fontsize=9)
        ax.set_facecolor("#0e0e10")
        ax.tick_params(colors="#aaa")
        ax.title.set_color("#ddd")
    fig.patch.set_facecolor("#1a1a1d")
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "wide_htf_dist.png"), dpi=110, facecolor=fig.get_facecolor())
    plt.close(fig)
    out += ["", "![HTF dist](screenshots/sprint4/wide_htf_dist.png)"]

    with open(REPORT, "w") as f:
        f.write("\n".join(out))
    print(f"\nReport: {REPORT}")


if __name__ == "__main__":
    main()
