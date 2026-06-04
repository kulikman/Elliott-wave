"""Sprint 0 — automated historical validation.

For each of 8 symbols × CTF/HTF pairs:
1. Download OHLC via yfinance
2. Run monowave detector + classifier + figure matcher
3. Compute HTF bias series
4. Render matplotlib chart with overlays → PNG
5. Aggregate metrics into a Markdown report
"""
from __future__ import annotations
import sys, os, warnings
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
warnings.filterwarnings("ignore")

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D

from ewb.monowaves import detect_monowaves
from ewb.rules import classify_pivots
from ewb.figures import match_figures, Figure
from ewb.htf import resample_ohlc, htf_bias_series
from ewb.research import download_ohlc


REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_DIR = os.path.join(REPO, "docs", "validation", "screenshots", "sprint0")
REPORT  = os.path.join(REPO, "docs", "validation", "sprint0-report.md")
os.makedirs(OUT_DIR, exist_ok=True)


# (ticker, ctf_interval, htf_pandas_rule, period, label)
SYMBOLS = [
    ("SPY",     "1d", "1W", "5y",  "SPY 1D / HTF 1W — длинный тренд"),
    ("BTC-USD", "4h", "1D", "2y",  "BTC 4H / HTF 1D — крипто-тренд"),
    ("EURUSD=X","1h", "4h", "60d", "EURUSD 1H / HTF 4H — флэт/форекс"),
    ("AAPL",    "1d", "1W", "5y",  "AAPL 1D / HTF 1W — чистые импульсы"),
    ("TSLA",    "4h", "1D", "1y",  "TSLA 4H / HTF 1D — хаотичный"),
    ("GC=F",    "1d", "1W", "5y",  "GOLD 1D / HTF 1W — длинные коррекции"),
    ("NQ=F",    "15m","1h", "30d", "NQ 15m / HTF 1H — intraday"),
    ("SOL-USD", "1h", "4h", "60d", "SOL 1H / HTF 4H — альткоин"),
]


def analyze(df: pd.DataFrame, htf_rule: str, atr_period=14, atr_mult=2.5):
    """Run full detector pipeline."""
    pivots = detect_monowaves(df, atr_period=atr_period, atr_mult=atr_mult)
    classify_pivots(pivots)
    figures = match_figures(pivots)
    # HTF bias series
    try:
        bias = htf_bias_series(df, htf_rule, atr_period=atr_period, atr_mult=atr_mult)
    except Exception as e:
        print(f"  HTF bias failed: {e}")
        bias = pd.Series(0, index=df.index)
    # HTF pivots for visualisation
    htf_df = resample_ohlc(df, htf_rule)
    htf_pivots = detect_monowaves(htf_df, atr_period=atr_period, atr_mult=atr_mult)
    return pivots, figures, bias, htf_df, htf_pivots


def plot_chart(df: pd.DataFrame, pivots, figures, bias, htf_df, htf_pivots,
               title: str, out_png: str):
    """Render matplotlib chart with all overlays."""
    fig, ax = plt.subplots(figsize=(18, 9))

    # Price line
    ax.plot(df.index, df["close"], color="#cccccc", linewidth=0.8, label="close")

    # HTF bias background — green/red bands
    if bias is not None and len(bias) > 0:
        # Build contiguous segments of same bias
        chg = (bias != bias.shift(1)).cumsum()
        for _, grp in bias.groupby(chg):
            if len(grp) < 2:
                continue
            v = int(grp.iloc[0])
            if v == 0:
                continue
            color = "#1a4d1a" if v > 0 else "#4d1a1a"
            alpha = 0.15 if abs(v) == 1 else 0.30
            ax.axvspan(grp.index[0], grp.index[-1], color=color, alpha=alpha, zorder=0)

    # CTF monowaves: connect pivots with coloured lines
    if pivots:
        x = [df.index[p.idx] for p in pivots]
        y = [p.price for p in pivots]
        # segments
        for i in range(1, len(pivots)):
            c = "#1f9b6a" if pivots[i].direction > 0 else "#d85060"
            ax.plot([x[i-1], x[i]], [y[i-1], y[i]],
                    color=c, linewidth=1.6, zorder=2)
        # pivot dots
        ax.scatter(x, y, c=["#1f9b6a" if p.direction > 0 else "#d85060" for p in pivots],
                   s=22, zorder=4, edgecolors="white", linewidths=0.6)
        # rule labels — only every 3rd to avoid clutter
        for i, p in enumerate(pivots):
            if p.rule_no > 0 and i % 3 == 0:
                txt = f"П{p.rule_no}{p.cond_letter}"
                ax.annotate(txt, (x[i], y[i]),
                            xytext=(0, 8), textcoords="offset points",
                            fontsize=6, color="#a050d0", ha="center", zorder=5)

    # HTF monowaves: dashed orange overlay
    if htf_pivots:
        for i in range(1, len(htf_pivots)):
            x0 = htf_df.index[htf_pivots[i-1].idx]
            x1 = htf_df.index[htf_pivots[i].idx]
            y0 = htf_pivots[i-1].price
            y1 = htf_pivots[i].price
            ax.plot([x0, x1], [y0, y1], color="#ff9020",
                    linewidth=2.0, linestyle="--", alpha=0.75, zorder=3)
        hx = [htf_df.index[p.idx] for p in htf_pivots]
        hy = [p.price for p in htf_pivots]
        ax.scatter(hx, hy, c="#ff9020", s=60, marker="D",
                   edgecolors="white", linewidths=0.8, zorder=5)

    # Figures: shaded rectangles + labels
    palette = {"impulse": "#22aa55", "flat": "#3399cc",
               "triangle": "#aa55cc", "double_corr": "#cc8800",
               "zigzag": "#888888"}
    for f in figures:
        if f.start_idx >= len(df) or f.end_idx >= len(df):
            continue
        x0 = df.index[f.start_idx]
        x1 = df.index[f.end_idx]
        prices = [p.price for p in f.pivots]
        lo, hi = min(prices), max(prices)
        col = palette.get(f.type, "#666666")
        alpha = 0.18 if f.confirmed else 0.08
        rect = mpatches.Rectangle((x0, lo), x1 - x0, hi - lo,
                                   facecolor=col, alpha=alpha,
                                   edgecolor=col, linewidth=1.4 if f.confirmed else 0.8,
                                   linestyle="-" if f.confirmed else ":",
                                   zorder=1)
        ax.add_patch(rect)
        marker = "✓" if f.confirmed else "?"
        ax.annotate(f"{f.type[:3]} {f.direction[:2]} {marker}",
                    (x0 + (x1 - x0) / 2, hi),
                    xytext=(0, 4), textcoords="offset points",
                    fontsize=7, color=col, ha="center",
                    weight="bold" if f.confirmed else "normal", zorder=6)

    # Legend
    handles = [
        Line2D([0],[0], color="#1f9b6a", lw=1.6, label="CTF моноволна ↑"),
        Line2D([0],[0], color="#d85060", lw=1.6, label="CTF моноволна ↓"),
        Line2D([0],[0], color="#ff9020", lw=2, linestyle="--", label="HTF моноволна"),
        mpatches.Patch(facecolor="#1a4d1a", alpha=0.3, label="HTF bull bias"),
        mpatches.Patch(facecolor="#4d1a1a", alpha=0.3, label="HTF bear bias"),
        mpatches.Patch(facecolor=palette["impulse"], alpha=0.5, label="Импульс"),
        mpatches.Patch(facecolor=palette["flat"], alpha=0.5, label="Плоская"),
        mpatches.Patch(facecolor=palette["triangle"], alpha=0.5, label="Треугольник"),
        mpatches.Patch(facecolor=palette["double_corr"], alpha=0.5, label="Двойн.Корр."),
    ]
    ax.legend(handles=handles, loc="upper left", fontsize=7, framealpha=0.9, ncol=2)
    ax.set_title(title, fontsize=12)
    ax.set_facecolor("#0e0e10")
    fig.patch.set_facecolor("#1a1a1d")
    ax.tick_params(colors="#aaaaaa")
    ax.title.set_color("#dddddd")
    for spine in ax.spines.values():
        spine.set_color("#444444")
    plt.tight_layout()
    plt.savefig(out_png, dpi=130, facecolor=fig.get_facecolor())
    plt.close(fig)


def figure_stats(figures: list[Figure]) -> dict:
    """Aggregate figure counts and confirmation rates."""
    out = {}
    types = ["impulse", "flat", "triangle", "double_corr"]
    for t in types:
        subset = [f for f in figures if f.type == t]
        confirmed = [f for f in subset if f.confirmed]
        out[t] = {
            "total": len(subset),
            "confirmed": len(confirmed),
            "rate": (len(confirmed) / len(subset)) if subset else 0.0,
        }
    out["all"] = {
        "total": len(figures),
        "confirmed": sum(1 for f in figures if f.confirmed),
        "rate": (sum(1 for f in figures if f.confirmed) / len(figures)) if figures else 0.0,
    }
    return out


def main():
    summary_rows = []
    detail_blocks = []

    for (ticker, interval, htf_rule, period, label) in SYMBOLS:
        print(f"\n=== {label} ===")
        try:
            df = download_ohlc(ticker, interval, period, include_volume=True, min_rows=0)
        except Exception as e:
            print(f"  download failed: {e}")
            continue
        if df is None:
            df = pd.DataFrame()
        if df.empty or len(df) < 50:
            print(f"  empty or too short ({len(df)} bars), skip")
            continue
        print(f"  bars: {len(df)}, range: {df.index[0]} → {df.index[-1]}")

        pivots, figures, bias, htf_df, htf_pivots = analyze(df, htf_rule)
        print(f"  CTF pivots: {len(pivots)}, HTF pivots: {len(htf_pivots)}, figures: {len(figures)}")

        stats = figure_stats(figures)
        final_bias = int(bias.iloc[-1]) if len(bias) else 0
        summary_rows.append({
            "label": label, "bars": len(df),
            "ctf_pivots": len(pivots), "htf_pivots": len(htf_pivots),
            "n_impulse": stats["impulse"]["total"],
            "n_flat": stats["flat"]["total"],
            "n_triangle": stats["triangle"]["total"],
            "n_double": stats["double_corr"]["total"],
            "total_fig": stats["all"]["total"],
            "confirmed_fig": stats["all"]["confirmed"],
            "confirm_rate": stats["all"]["rate"],
            "final_htf_bias": final_bias,
        })

        # render
        safe = ticker.replace("=", "").replace("-", "").replace("/", "").lower()
        png = os.path.join(OUT_DIR, f"{safe}-{interval}.png")
        plot_chart(df, pivots, figures, bias, htf_df, htf_pivots, label, png)
        print(f"  saved: {png}")

        # detail block
        block_lines = [f"## {label}", "",
                       f"- Период: `{df.index[0].date()} → {df.index[-1].date()}` ({len(df)} баров)",
                       f"- CTF моноволн: **{len(pivots)}**, HTF моноволн: **{len(htf_pivots)}**",
                       f"- Финальный HTF bias: **{final_bias}** ({'STRONG BULL' if final_bias==2 else 'WEAK BULL' if final_bias==1 else 'FLAT' if final_bias==0 else 'WEAK BEAR' if final_bias==-1 else 'STRONG BEAR'})",
                       "",
                       "| Тип фигуры | Всего | Подтверждено | Rate |",
                       "|---|---|---|---|"]
        for t in ["impulse", "flat", "triangle", "double_corr"]:
            s = stats[t]
            block_lines.append(f"| {t} | {s['total']} | {s['confirmed']} | {s['rate']*100:.0f}% |")
        block_lines.append(f"| **ВСЕГО** | **{stats['all']['total']}** | **{stats['all']['confirmed']}** | **{stats['all']['rate']*100:.0f}%** |")
        block_lines.append("")
        block_lines.append(f"![{label}](screenshots/sprint0/{safe}-{interval}.png)")
        block_lines.append("")
        detail_blocks.append("\n".join(block_lines))

    # Write report
    md = []
    md.append("# Спринт 0 — Авто-валидация (Python)")
    md.append("")
    md.append("**Сгенерировано автоматически:** `python/scripts/validate_sprint0.py`")
    md.append(f"**Дата:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}")
    md.append("")
    md.append("## Сводка по тикерам")
    md.append("")
    md.append("| Тикер / ТФ | Баров | CTF пив | HTF пив | Имп | Флэт | Треуг | DC | Всего | ✓Подтв. | Rate | HTF bias |")
    md.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in summary_rows:
        bias_str = {2:"▲▲", 1:"▲", 0:"━", -1:"▼", -2:"▼▼"}[r["final_htf_bias"]]
        md.append(f"| {r['label'][:30]} | {r['bars']} | {r['ctf_pivots']} | {r['htf_pivots']} | "
                  f"{r['n_impulse']} | {r['n_flat']} | {r['n_triangle']} | {r['n_double']} | "
                  f"{r['total_fig']} | {r['confirmed_fig']} | {r['confirm_rate']*100:.0f}% | {bias_str} |")
    md.append("")

    # Totals
    total_figs = sum(r["total_fig"] for r in summary_rows)
    total_confirmed = sum(r["confirmed_fig"] for r in summary_rows)
    overall_rate = total_confirmed / total_figs if total_figs else 0
    md.append("## Итог")
    md.append("")
    md.append(f"- Всего распознано фигур: **{total_figs}**")
    md.append(f"- Из них подтверждено (passed Error-rules): **{total_confirmed}**")
    md.append(f"- Confirm rate: **{overall_rate*100:.1f}%**")
    md.append("")
    md.append("**Gate Спринта 0:**")
    md.append("")
    md.append("- ✅ ≥70% подтверждённых фигур → переход в Спринт 1 (HTF bias UI)")
    md.append("- ⚠ 50-70% → Спринт 0.5: тюнинг ATR multiplier / диагностика ошибок")
    md.append("- ❌ <50% → пересмотр алгоритма")
    md.append("")
    md.append("---")
    md.append("")
    md.extend(detail_blocks)

    with open(REPORT, "w") as f:
        f.write("\n".join(md))
    print(f"\nReport written: {REPORT}")
    print(f"Overall confirm rate: {overall_rate*100:.1f}%")


if __name__ == "__main__":
    main()
