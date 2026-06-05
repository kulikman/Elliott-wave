"""Sprint 6.5 — strategy variants.

Test on the same 10k figures dataset:

V1. fade-fixed-N      — fade figure, exit at fixed N bars (baseline)
V2. fade-tp-sl        — fade with TP=fig_start, SL=fig_end+amp, time exit N
V3. follow-fixed-N    — follow figure direction (REVERSE of fade)
V4. follow-tp-sl      — follow with mirror TP/SL
V5. per-type best     — fade for flat/DC, follow for triangle/impulse

Each variant × multiple horizons (5, 10, 20, 50). Output:
- docs/validation/sprint6-variants.md (grid)
- screenshots/sprint6/variants_*.png (equity for best ones)

Key question: does triangle FOLLOW give +Sharpe (since fade gave -2.83)?
"""
from __future__ import annotations
import sys, os, warnings, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from ewb.monowaves import detect_monowaves
from ewb.rules import classify_pivots
from ewb.figures import match_figures
from ewb.htf import htf_bias_series
from ewb.research import (
    SYMBOLS,
    cost_for,
    download_ohlc,
    exit_for_trade,
    log_processing_error,
    portfolio_metrics,
)


REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_DIR = os.path.join(REPO, "docs", "validation", "screenshots", "sprint6")
REPORT  = os.path.join(REPO, "docs", "validation", "sprint6-variants.md")
os.makedirs(OUT_DIR, exist_ok=True)

INTERVALS = [("1d","1W","5y"), ("1h","1D","730d")]

def simulate_one(df, figs, bias, ticker, interval,
                 strategy="fade", exit_bars=20, use_tp_sl=False):
    """Generate trades for one symbol under given strategy."""
    close = df["close"].to_numpy()
    high  = df["high"].to_numpy()
    low   = df["low"].to_numpy()
    n = len(close)
    cost = cost_for(ticker)
    trades = []

    for f in figs:
        if not f.confirmed:
            continue
        entry_idx = f.pivots[-1].confirmation_idx
        if entry_idx < 0: entry_idx = f.end_idx
        if entry_idx + exit_bars >= n: continue
        bias_val = int(bias.iloc[entry_idx]) if entry_idx < len(bias) else 0
        with_htf = (f.direction == "up" and bias_val > 0) or \
                   (f.direction == "down" and bias_val < 0)
        entry_px = close[entry_idx]
        if entry_px <= 0 or np.isnan(entry_px): continue

        # Direction
        if strategy == "fade":
            side = -1 if f.direction == "up" else +1
        elif strategy == "follow":
            side = +1 if f.direction == "up" else -1
        else:
            continue
        amp = f.amplitude
        exit_idx, exit_px, reason = exit_for_trade(
            high, low, close, entry_idx, entry_px, side, exit_bars, amp, use_tp_sl
        )

        raw = side * (exit_px - entry_px) / entry_px
        net = raw - 2 * cost
        trades.append({
            "ticker": ticker, "interval": interval,
            "fig_type": f.type, "direction": f.direction,
            "with_htf": with_htf,
            "side": "long" if side==1 else "short",
            "entry_ts": df.index[entry_idx],
            "exit_ts": df.index[exit_idx],
            "bars_held": exit_idx - entry_idx,
            "entry_px": entry_px, "exit_px": exit_px,
            "amp_pct": amp / entry_px if entry_px else np.nan,
            "raw_ret": raw, "net_ret": net,
            "win": net > 0, "exit_reason": reason,
        })
    return trades


def simulate_all(strategy, exit_bars, use_tp_sl):
    """Run all symbols × intervals with given parameters."""
    all_trades = []
    for ticker in SYMBOLS:
        for (interval, htf_rule, period) in INTERVALS:
            df = download_ohlc(ticker, interval, period, min_rows=100)
            if df is None: continue
            try:
                p = detect_monowaves(df, atr_mult=2.5)
                classify_pivots(p)
                f = match_figures(p)
                b = htf_bias_series(df, htf_rule)
            except Exception as exc:
                log_processing_error(ticker, interval, exc)
                continue
            all_trades.extend(simulate_one(df, f, b, ticker, interval,
                                           strategy, exit_bars, use_tp_sl))
    return pd.DataFrame(all_trades)


def main():
    t0 = time.time()
    results = []

    # 4 strategy × 3 horizons × {tp_sl, time-only} = 24 variants
    configs = []
    for strat in ["fade", "follow"]:
        for bars in [10, 20, 50]:
            for tp_sl in [False, True]:
                configs.append((strat, bars, tp_sl))

    cache = {}
    for i, (strat, bars, tp_sl) in enumerate(configs):
        key = (strat, bars, tp_sl)
        print(f"[{i+1:2}/{len(configs)}] {strat} bars={bars} tp_sl={tp_sl} ...", end=" ", flush=True)
        # Cache by (strat, bars, tp_sl) — each unique
        trades = simulate_all(strat, bars, tp_sl)
        # Overall portfolio
        m_all = portfolio_metrics(trades)
        if m_all:
            results.append({
                "strategy": strat, "exit_bars": bars, "tp_sl": tp_sl,
                "subset": "ALL",
                "n": m_all["n"], "cagr": m_all["cagr_pct"],
                "sharpe": m_all["sharpe"], "dd": m_all["max_dd"],
                "calmar": m_all["calmar"], "win": m_all["win_rate"],
                "total": m_all["total_pct"],
            })
        # Per fig type
        for ft in ["impulse","flat","triangle","double_corr"]:
            sub = trades[trades["fig_type"]==ft]
            if len(sub) < 30: continue
            m = portfolio_metrics(sub)
            if m:
                results.append({
                    "strategy": strat, "exit_bars": bars, "tp_sl": tp_sl,
                    "subset": ft,
                    "n": m["n"], "cagr": m["cagr_pct"],
                    "sharpe": m["sharpe"], "dd": m["max_dd"],
                    "calmar": m["calmar"], "win": m["win_rate"],
                    "total": m["total_pct"],
                })
        print(f"({time.time()-t0:.0f}s)")
        cache[key] = trades

    df_res = pd.DataFrame(results)

    lines = [
        "# Спринт 6.5 — Strategy variants",
        "",
        f"**Дата:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "Тестируем 12 комбинаций (fade/follow × 10/20/50 bars × time/TP-SL) ",
        "на полном 10k-датасете. Position sizing: 1% риск, max 10 параллельных.",
        "",
        "## Главный вопрос",
        "",
        "Triangle на fade дал Sharpe **-2.83**. Если перевернуть в **follow**, ",
        "получим ли +Sharpe? Если да — Triangle прорывы устойчивы.",
        "",
        "## Sharpe-таблица по подвыборкам (топ-2 строки каждой подгруппы)",
        ""
    ]

    # Pivot: rows = subset, cols = (strategy, exit_bars, tp_sl), values = sharpe
    pivot_sharpe = df_res.pivot_table(
        index="subset",
        columns=["strategy","exit_bars","tp_sl"],
        values="sharpe",
        aggfunc="first"
    )
    lines.append("```")
    lines.append(pivot_sharpe.round(2).to_string())
    lines.append("```")
    lines.append("")

    lines += ["## Лучшие конфигурации (по Calmar)", "",
              "| subset | strategy | bars | tp_sl | n | CAGR | Sharpe | DD | Calmar | Win |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    top = df_res.sort_values("calmar", ascending=False).head(20)
    for _, r in top.iterrows():
        lines.append(f"| {r['subset']} | {r['strategy']} | {r['exit_bars']} | "
                     f"{'tp/sl' if r['tp_sl'] else 'time'} | {r['n']:.0f} | "
                     f"{r['cagr']:.1f}% | {r['sharpe']:.2f} | {r['dd']:.1f}% | "
                     f"{r['calmar']:.2f} | {r['win']:.1f}% |")

    # Triangle specific — main question
    lines += ["", "## Triangle: fade vs follow", "",
              "| bars | tp_sl | fade Sharpe | follow Sharpe | fade CAGR | follow CAGR |",
              "|---|---|---|---|---|---|"]
    tri = df_res[df_res["subset"]=="triangle"]
    for bars in [10, 20, 50]:
        for tp_sl in [False, True]:
            f_row = tri[(tri["strategy"]=="fade") & (tri["exit_bars"]==bars) & (tri["tp_sl"]==tp_sl)]
            fo_row = tri[(tri["strategy"]=="follow") & (tri["exit_bars"]==bars) & (tri["tp_sl"]==tp_sl)]
            if f_row.empty or fo_row.empty: continue
            f = f_row.iloc[0]; fo = fo_row.iloc[0]
            lines.append(f"| {bars} | {'tp/sl' if tp_sl else 'time'} | "
                         f"{f['sharpe']:.2f} | {fo['sharpe']:.2f} | "
                         f"{f['cagr']:.1f}% | {fo['cagr']:.1f}% |")

    # Save best variant equity curve
    best = df_res.sort_values("calmar", ascending=False).iloc[0]
    bk = (best["strategy"], int(best["exit_bars"]), bool(best["tp_sl"]))
    best_trades = cache[bk]
    if best["subset"] != "ALL":
        best_trades = best_trades[best_trades["fig_type"]==best["subset"]]
    m_best = portfolio_metrics(best_trades)
    if m_best and "eq_curve" in m_best:
        eq = m_best["eq_curve"]
        fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True,
                                 gridspec_kw={"height_ratios":[3,1]})
        axes[0].plot(eq["ts"], eq["eq"], color="#22cc77", linewidth=1.3)
        axes[0].axhline(100000, color="white", lw=0.7, ls="--", alpha=0.4)
        title = (f"BEST: {best['subset']} / {best['strategy']} / bars={best['exit_bars']} / "
                 f"{'tp_sl' if best['tp_sl'] else 'time'} — "
                 f"CAGR={best['cagr']:.1f}% Sharpe={best['sharpe']:.2f} DD={best['dd']:.1f}%")
        axes[0].set_title(title, color="#ddd"); axes[0].set_ylabel("equity $", color="#aaa")
        axes[0].set_facecolor("#0e0e10"); axes[0].tick_params(colors="#aaa")
        for s in axes[0].spines.values(): s.set_color("#444")
        peak = eq["eq"].cummax()
        dd = (eq["eq"]/peak - 1)*100
        axes[1].fill_between(eq["ts"], dd, 0, color="#cc3344", alpha=0.6)
        axes[1].set_ylabel("DD %", color="#aaa")
        axes[1].set_facecolor("#0e0e10"); axes[1].tick_params(colors="#aaa")
        for s in axes[1].spines.values(): s.set_color("#444")
        fig.patch.set_facecolor("#1a1a1d")
        plt.tight_layout()
        plt.savefig(os.path.join(OUT_DIR, "variants_best.png"), dpi=110,
                    facecolor=fig.get_facecolor())
        plt.close(fig)
        lines += ["", "## Equity лучшей конфигурации", "",
                  "![Best](screenshots/sprint6/variants_best.png)"]

    with open(REPORT, "w") as f:
        f.write("\n".join(lines))
    print(f"\nReport: {REPORT}")
    print(f"BEST: {best['subset']} / {best['strategy']} / bars={best['exit_bars']} / "
          f"{'tp_sl' if best['tp_sl'] else 'time'} — Sharpe {best['sharpe']:.2f} Calmar {best['calmar']:.2f}")


if __name__ == "__main__":
    main()
