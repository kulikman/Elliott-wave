"""Sprint 4 — Edge discovery on detected figures.

For each detected figure, compute future returns N bars after figure ends.
Test 4 hypotheses about whether Elliott figures give a directional edge.

Output: docs/validation/sprint4-edge.md + figures/sprint4/*.png
"""
from __future__ import annotations
import sys, os, warnings
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from ewb.monowaves import detect_monowaves
from ewb.rules import classify_pivots
from ewb.figures import match_figures
from ewb.htf import htf_bias_series
from ewb.research import download_ohlc, fmt_df, hypothesis_table, log_processing_error, t_test


REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_DIR = os.path.join(REPO, "docs", "validation", "screenshots", "sprint4")
REPORT  = os.path.join(REPO, "docs", "validation", "sprint4-edge.md")
os.makedirs(OUT_DIR, exist_ok=True)


# Symbols & params — same as Sprint 0 for consistency
SYMBOLS = [
    ("SPY",     "1d", "1W", "5y"),
    ("BTC-USD", "4h", "1D", "2y"),
    ("EURUSD=X","1h", "4h", "60d"),
    ("AAPL",    "1d", "1W", "5y"),
    ("TSLA",    "4h", "1D", "1y"),
    ("GC=F",    "1d", "1W", "5y"),
    ("NQ=F",    "15m","1h", "30d"),
    ("SOL-USD", "1h", "4h", "60d"),
]

HORIZONS = [5, 10, 20, 50]   # bars ahead


def build_dataset() -> pd.DataFrame:
    """One row per figure with features + future returns."""
    rows = []
    for ticker, interval, htf_rule, period in SYMBOLS:
        print(f"  {ticker} {interval}...", end=" ", flush=True)
        try:
            df = download_ohlc(ticker, interval, period, min_rows=0)
        except Exception as e:
            log_processing_error(ticker, interval, e, context="download")
            continue
        if df is None:
            print("no data"); continue
        if len(df) < 100:
            print("too short"); continue
        pivots = detect_monowaves(df, atr_mult=2.5)
        classify_pivots(pivots)
        figs = match_figures(pivots)
        try:
            bias = htf_bias_series(df, htf_rule)
        except Exception as e:
            log_processing_error(ticker, interval, e, context="htf_bias")
            bias = pd.Series(0, index=df.index)

        close = df["close"].to_numpy()
        for f in figs:
            # ENTRY = confirmation bar of LAST pivot, not the extremum.
            # This is when we could realistically know the figure ended.
            entry_idx = f.pivots[-1].confirmation_idx
            if entry_idx < 0:
                entry_idx = f.end_idx  # fallback
            if entry_idx >= len(close) - max(HORIZONS):
                continue
            entry_px = close[entry_idx]
            # HTF bias also read at entry_idx (not at extremum)
            bias_val = int(bias.iloc[entry_idx]) if entry_idx < len(bias) else 0
            confirmation_lag = entry_idx - f.end_idx  # bars between extremum and confirmation
            row = {
                "ticker": ticker, "interval": interval,
                "end_ts": df.index[f.end_idx],
                "entry_ts": df.index[entry_idx],
                "confirmation_lag": confirmation_lag,
                "fig_type": f.type, "direction": f.direction,
                "confirmed": f.confirmed,
                "duration": f.duration,
                "amplitude": f.amplitude,
                "amp_pct": f.amplitude / entry_px,
                "htf_bias": bias_val,
                "n_errors": sum(1 for c in f.checks if c.severity=="E" and not c.ok),
                "n_warnings": sum(1 for c in f.checks if c.severity=="W" and not c.ok),
                "entry_px": entry_px,
            }
            for h in HORIZONS:
                if entry_idx + h < len(close):
                    fut = close[entry_idx + h]
                    row[f"ret_{h}"] = (fut - entry_px) / entry_px
                    # Сигнальный return: знак выровнен с прогнозом Эллиота
                    # Импульс ↑ → ожидаем коррекция ↓ → signed_ret = -ret
                    # Импульс ↓ → ожидаем коррекция ↑ → signed_ret = -ret
                    # Коррекция (flat/zigzag/triangle/double) ↑ → ожидаем продолжение тренда ↓
                    #   → знак противоположен direction коррекции = -ret для up корр.
                    # Упрощённо: для всех фигур "следующая волна противоположна последней"
                    # signed_ret > 0 → прогноз сбылся
                    sign = -1 if f.direction == "up" else +1
                    row[f"signed_ret_{h}"] = row[f"ret_{h}"] * sign
                else:
                    row[f"ret_{h}"] = np.nan
                    row[f"signed_ret_{h}"] = np.nan
            rows.append(row)
        print(f"{len(figs)} figs")
    return pd.DataFrame(rows)


def plot_distribution(df, horizon, signal_col, title, fname):
    fig, ax = plt.subplots(figsize=(10, 5))
    s = df[f"{signal_col}_{horizon}"].dropna()
    ax.hist(s * 100, bins=40, color="#3399cc", alpha=0.7, edgecolor="white")
    ax.axvline(0, color="white", linestyle="--", linewidth=1)
    ax.axvline(s.mean() * 100, color="#22cc55", linewidth=2, label=f"mean={s.mean()*100:.2f}%")
    ax.set_title(f"{title}\nn={len(s)}, hit={((s>0).mean())*100:.1f}%, mean={s.mean()*100:.2f}%, "
                 f"σ={s.std()*100:.2f}%")
    ax.set_xlabel("signed return %")
    ax.set_ylabel("count")
    ax.legend()
    ax.set_facecolor("#0e0e10")
    fig.patch.set_facecolor("#1a1a1d")
    ax.tick_params(colors="#aaaaaa")
    ax.title.set_color("#dddddd")
    ax.xaxis.label.set_color("#aaaaaa")
    ax.yaxis.label.set_color("#aaaaaa")
    for spine in ax.spines.values():
        spine.set_color("#444444")
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, fname), dpi=110, facecolor=fig.get_facecolor())
    plt.close(fig)


def walk_forward_split(df: pd.DataFrame, train_frac=0.5):
    """Split by time per ticker."""
    train_parts, test_parts = [], []
    for tk, grp in df.groupby("ticker"):
        grp = grp.sort_values("end_ts")
        n = len(grp)
        cut = int(n * train_frac)
        train_parts.append(grp.iloc[:cut])
        test_parts.append(grp.iloc[cut:])
    return pd.concat(train_parts), pd.concat(test_parts)


def main():
    print("Building dataset...")
    df = build_dataset()
    print(f"\nTotal figures with future data: {len(df)}")
    df.to_parquet(os.path.join(REPO, "python", "data", "figures.parquet"))
    print(f"Saved: python/data/figures.parquet")

    lines = ["# Спринт 4 — Edge Discovery", "",
             f"**Дата:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}",
             f"**Датасет:** {len(df)} фигур, {df['ticker'].nunique()} тикеров",
             "",
             "## Соглашение о знаке (`signed_ret`)",
             "",
             "Эллиот говорит: после фигуры следующая волна **противоположна направлению фигуры**.",
             "- Импульс ↑ закончился → ожидаем коррекцию ↓",
             "- Импульс ↓ закончился → ожидаем коррекцию ↑",
             "- Коррекция (flat/triangle/etc) ↑ закончилась → ожидаем продолжение тренда ↓",
             "",
             "`signed_ret_N = -ret_N if figure.direction=='up' else +ret_N`",
             "",
             "**signed_ret > 0 → прогноз Эллиота сбылся**. hit_rate = `% случаев когда сбылся`.",
             "",
             "**Случайный baseline:** ~50%. Edge ≥ 55% = устойчиво (для финансов с комиссиями нужно ≥55-58%).",
             ""]

    # ─── H0: Baseline — все фигуры все горизонты ────────────────
    lines += ["## H0 — Baseline по всем фигурам", "",
              "| Горизонт | n | hit_rate | mean_ret | Sharpe | p-value |",
              "|---|---|---|---|---|---|"]
    for h in HORIZONS:
        s = df[f"signed_ret_{h}"].dropna()
        if len(s) == 0: continue
        t, p = t_test(s)
        sh = s.mean()/s.std() if s.std()>0 else np.nan
        lines.append(f"| {h} | {len(s)} | {(s>0).mean()*100:.1f}% | {s.mean()*100:.2f}% | {sh:.3f} | {p:.4f} |")
    lines += [""]

    # Distribution plots per horizon
    for h in HORIZONS:
        plot_distribution(df, h, "signed_ret", f"All figures — signed_ret_{h}",
                         f"h0_all_h{h}.png")

    # ─── H1: По типу фигуры ────────────────
    lines += ["## H1 — Edge по типу фигуры (ret_20)", "",
              "Подразумевается: разные фигуры → разные прогнозы.", ""]
    tab = hypothesis_table(df, ["fig_type"], 20, "signed_ret")
    if not tab.empty:
        lines.append(fmt_df(tab.sort_values("hit_rate", ascending=False),
                            cols_pct=["hit_rate","mean_ret"], cols_round=["sharpe","t_stat","p_value"]))
    lines += [""]

    # ─── H2: HTF bias as filter ────────────────
    lines += ["## H2 — Влияние HTF bias на edge (ret_20)", "",
              "Гипотеза: с трендом HTF → коррекции отрабатывают чаще.", ""]
    df_with_bias = df.copy()
    df_with_bias["with_htf"] = df_with_bias.apply(
        lambda r: (r["direction"]=="up" and r["htf_bias"]>0) or
                  (r["direction"]=="down" and r["htf_bias"]<0), axis=1)
    tab = hypothesis_table(df_with_bias, ["fig_type", "with_htf"], 20, "signed_ret")
    if not tab.empty:
        lines.append(fmt_df(tab.sort_values(["fig_type","with_htf"]),
                            cols_pct=["hit_rate","mean_ret"], cols_round=["sharpe","t_stat","p_value"]))
    lines += [""]

    # ─── H3: Confirmed vs not ────────────────
    lines += ["## H3 — Confirmed vs unconfirmed (ret_20)", ""]
    tab = hypothesis_table(df, ["fig_type", "confirmed"], 20, "signed_ret")
    if not tab.empty:
        lines.append(fmt_df(tab.sort_values(["fig_type","confirmed"]),
                            cols_pct=["hit_rate","mean_ret"], cols_round=["sharpe","t_stat","p_value"]))
    lines += [""]

    # ─── H4: Walk-forward stability ────────────────
    lines += ["## H4 — Walk-forward (первая vs вторая половина истории)", "",
              "Если edge есть только в train и нет в test → переобучение / случайность.",
              ""]
    train, test = walk_forward_split(df, train_frac=0.5)
    lines += ["### Train (первая половина)", ""]
    tab = hypothesis_table(train, ["fig_type"], 20, "signed_ret")
    if not tab.empty:
        lines.append(fmt_df(tab.sort_values("hit_rate", ascending=False),
                            cols_pct=["hit_rate","mean_ret"], cols_round=["sharpe","t_stat","p_value"]))
    lines += ["", "### Test (вторая половина)", ""]
    tab = hypothesis_table(test, ["fig_type"], 20, "signed_ret")
    if not tab.empty:
        lines.append(fmt_df(tab.sort_values("hit_rate", ascending=False),
                            cols_pct=["hit_rate","mean_ret"], cols_round=["sharpe","t_stat","p_value"]))
    lines += [""]

    # ─── Summary / gate ────────────────
    lines += ["## Финальный вердикт", ""]
    # Find best hypothesis (highest hit_rate with n>=20, p<0.10)
    best_lines = []
    for h in HORIZONS:
        tab = hypothesis_table(df, ["fig_type"], h, "signed_ret")
        if tab.empty: continue
        candidates = tab[(tab["n"]>=20) & (tab["p_value"]<0.10)]
        if not candidates.empty:
            best = candidates.sort_values("hit_rate", ascending=False).iloc[0]
            best_lines.append(f"- h={h}: **{best['fig_type']}** hit={best['hit_rate']*100:.1f}% "
                              f"n={int(best['n'])} mean={best['mean_ret']*100:.2f}% "
                              f"p={best['p_value']:.3f}")
    if best_lines:
        lines += ["**Статистически значимые edge-комбинации (p<0.10):**", ""]
        lines += best_lines
        lines += [""]
        lines += ["**Gate Спринта 4:** edge найден → переход в Спринт 3 (расширенный датасет)"]
    else:
        lines += ["**Статистически значимых edge на текущей выборке не найдено** (n=243 мало).",
                  "",
                  "**Решение:**",
                  "1. Расширить выборку (Спринт 3 — 50+ тикеров × 5 лет = 5-10k фигур)",
                  "2. Передоопределить signed_ret (возможно прогноз должен быть по типу фигуры)",
                  "3. Добавить тонкие features (длительность, амплитуда, ratio) — но это уже ML"]

    with open(REPORT, "w") as f:
        f.write("\n".join(lines))
    print(f"\nReport: {REPORT}")


if __name__ == "__main__":
    main()
