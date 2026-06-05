"""Sprint 6 — Backtest "fade-with-HTF" strategy.

Strategy:
  After a figure ends ON SIDE of HTF bias (with_htf=True), enter against figure
  direction (Elliott correction).
  - HTF bull + figure UP   → SHORT
  - HTF bear + figure DOWN → LONG

Exit modes (compared):
  A. fixed_N — close after N=20 bars
  B. tp_sl   — TP at figure_start_price, SL at figure_end_price + 1×amplitude

Costs:
  commission_per_side = 0.05% (stocks), 0.10% (crypto/FX/futures)
  slippage_per_side   = 0.03%

Outputs:
  - docs/validation/sprint6-backtest.md (per-strategy table + equity png)
  - docs/validation/screenshots/sprint6/*.png
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
    fmt_trade_metrics as fmt_metrics,
    log_processing_error,
    trade_metrics as metrics,
)


REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_DIR = os.path.join(REPO, "docs", "validation", "screenshots", "sprint6")
REPORT  = os.path.join(REPO, "docs", "validation", "sprint6-backtest.md")
os.makedirs(OUT_DIR, exist_ok=True)

INTERVALS = [("1d","1W","5y"), ("1h","1D","730d")]

def simulate_trades(symbols=SYMBOLS, intervals=INTERVALS,
                    n_bars_exit=20, fig_filter=None) -> pd.DataFrame:
    """Generate one row per trade with realised PnL after costs."""
    trades = []
    t0 = time.time()
    total = len(symbols) * len(intervals)
    done = 0
    for ticker in symbols:
        for (interval, htf_rule, period) in intervals:
            done += 1
            df = download_ohlc(ticker, interval, period, min_rows=100)
            if df is None: continue
            try:
                pivots = detect_monowaves(df, atr_mult=2.5)
                classify_pivots(pivots)
                figs = match_figures(pivots)
                bias = htf_bias_series(df, htf_rule)
            except Exception as exc:
                log_processing_error(ticker, interval, exc)
                continue

            close = df["close"].to_numpy()
            high  = df["high"].to_numpy()
            low   = df["low"].to_numpy()
            n = len(close)
            cost = cost_for(ticker)

            for f in figs:
                if not f.confirmed:
                    continue
                if fig_filter and f.type not in fig_filter:
                    continue
                entry_idx = f.pivots[-1].confirmation_idx
                if entry_idx < 0: entry_idx = f.end_idx
                if entry_idx + n_bars_exit >= n: continue

                bias_val = int(bias.iloc[entry_idx]) if entry_idx < len(bias) else 0
                with_htf = (f.direction == "up" and bias_val > 0) or \
                           (f.direction == "down" and bias_val < 0)
                if not with_htf: continue   # strategy: only with_htf

                entry_px = close[entry_idx]
                if entry_px <= 0 or np.isnan(entry_px): continue

                # Trade direction: opposite to figure (fade)
                side = -1 if f.direction == "up" else +1  # -1 short, +1 long

                amp = f.amplitude
                exit_idx, exit_px, exit_reason = exit_for_trade(
                    high, low, close, entry_idx, entry_px, side, n_bars_exit, amp
                )

                # Raw return per side
                raw_ret = side * (exit_px - entry_px) / entry_px
                # Round-trip cost (entry + exit, each side)
                net_ret = raw_ret - 2 * cost

                trades.append({
                    "ticker": ticker,
                    "interval": interval,
                    "fig_type": f.type,
                    "direction": f.direction,
                    "side": "short" if side == -1 else "long",
                    "entry_ts": df.index[entry_idx],
                    "exit_ts": df.index[exit_idx],
                    "bars_held": exit_idx - entry_idx,
                    "entry_px": entry_px,
                    "exit_px": exit_px,
                    "amp_pct": amp / entry_px,
                    "raw_ret": raw_ret,
                    "net_ret": net_ret,
                    "exit_reason": exit_reason,
                    "win": net_ret > 0,
                    "cost_per_side": cost,
                })
            elapsed = time.time() - t0
            print(f"[{done:3}/{total}] {ticker:10} {interval:3} → trades so far: {len(trades)}  ({elapsed:.0f}s)")
    return pd.DataFrame(trades)


def plot_equity(trades: pd.DataFrame, title: str, fname: str):
    if trades.empty: return
    sorted_t = trades.sort_values("entry_ts").copy()
    sorted_t["eq"] = (1 + sorted_t["net_ret"]).cumprod()
    sorted_t["eq_raw"] = (1 + sorted_t["raw_ret"]).cumprod()

    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True,
                             gridspec_kw={"height_ratios":[3,1]})
    axes[0].plot(sorted_t["entry_ts"], sorted_t["eq"], color="#22cc77",
                 linewidth=1.5, label="net (after costs)")
    axes[0].plot(sorted_t["entry_ts"], sorted_t["eq_raw"], color="#88ccff",
                 linewidth=1, alpha=0.5, label="raw (before costs)")
    axes[0].axhline(1, color="white", lw=0.7, ls="--", alpha=0.4)
    axes[0].set_title(title, color="#ddd")
    axes[0].set_ylabel("equity (×)", color="#aaa")
    axes[0].legend(loc="upper left")
    axes[0].set_facecolor("#0e0e10")
    axes[0].tick_params(colors="#aaa")
    for s in axes[0].spines.values(): s.set_color("#444")

    # Drawdown
    peak = sorted_t["eq"].cummax()
    dd = (sorted_t["eq"] / peak - 1) * 100
    axes[1].fill_between(sorted_t["entry_ts"], dd, 0, color="#cc3344", alpha=0.6)
    axes[1].set_ylabel("DD %", color="#aaa")
    axes[1].set_facecolor("#0e0e10")
    axes[1].tick_params(colors="#aaa")
    for s in axes[1].spines.values(): s.set_color("#444")

    fig.patch.set_facecolor("#1a1a1d")
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, fname), dpi=110, facecolor=fig.get_facecolor())
    plt.close(fig)


def main():
    print(f"=== Sprint 6 backtest ===")
    print(f"Generating trades (this hits yfinance — ~80s)...")
    trades = simulate_trades(n_bars_exit=20)
    print(f"\nTotal trades: {len(trades)}")
    if trades.empty:
        print("No trades — abort")
        return

    # Normalise timestamps to UTC (1d is tz-naive, 1h is tz-aware)
    trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
    trades["exit_ts"]  = pd.to_datetime(trades["exit_ts"], utc=True)
    trades_path = os.path.join(REPO, "python", "data", "trades_sprint6.parquet")
    trades.to_parquet(trades_path)
    print(f"Saved: {trades_path}")

    lines = ["# Спринт 6 — Backtest «fade with HTF»",
             "",
             f"**Дата:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}",
             f"**Сделок:** {len(trades)}",
             "",
             "## Стратегия", "",
             "**Вход:** в конце фигуры (entry_idx=confirmation бар), ТОЛЬКО если фигура совпадает с HTF биасом (with_htf=True).",
             "- HTF bull + figure UP → **SHORT** (ожидаем коррекция Эллиота вниз)",
             "- HTF bear + figure DOWN → **LONG**",
             "",
             "**Выход:** первый из трёх",
             "- TP = вход − amplitude (полный ретрейс фигуры в обратную сторону)",
             "- SL = вход + amplitude (фигура продолжается)",
             "- Time exit = 20 баров",
             "",
             "**Комиссии:** stocks/ETF — 0.08% per side; crypto/FX/commodities — 0.13% per side.",
             "",
             "## Общая статистика", ""]
    m_all = metrics(trades)
    lines.append(fmt_metrics(m_all))
    lines += ["", "## По типу фигуры", "",
              "| fig_type | n | win% | mean_net | total | DD | PF | Sharpe~ |",
              "|---|---|---|---|---|---|---|---|"]
    for ft, grp in trades.groupby("fig_type"):
        m = metrics(grp)
        if not m: continue
        lines.append(f"| {ft} | {m['n_trades']} | {m['win_rate']*100:.1f}% | "
                     f"{m['mean_ret']*100:.2f}% | {m['total_ret']*100:.1f}% | "
                     f"{m['max_dd']*100:.1f}% | {m['profit_factor']:.2f} | {m['sharpe_naive']:.2f} |")

    lines += ["", "## По таймфрейму", "",
              "| interval | n | win% | mean_net | total | DD | PF |",
              "|---|---|---|---|---|---|---|"]
    for itv, grp in trades.groupby("interval"):
        m = metrics(grp)
        if not m: continue
        lines.append(f"| {itv} | {m['n_trades']} | {m['win_rate']*100:.1f}% | "
                     f"{m['mean_ret']*100:.2f}% | {m['total_ret']*100:.1f}% | "
                     f"{m['max_dd']*100:.1f}% | {m['profit_factor']:.2f} |")

    lines += ["", "## По стороне (long vs short)", "",
              "| side | n | win% | mean_net | total |",
              "|---|---|---|---|---|"]
    for s, grp in trades.groupby("side"):
        m = metrics(grp)
        if not m: continue
        lines.append(f"| {s} | {m['n_trades']} | {m['win_rate']*100:.1f}% | "
                     f"{m['mean_ret']*100:.2f}% | {m['total_ret']*100:.1f}% |")

    lines += ["", "## Распределение exit reason", "",
              "| reason | n | % |",
              "|---|---|---|"]
    ec = trades["exit_reason"].value_counts()
    for r, c in ec.items():
        lines.append(f"| {r} | {c} | {c/len(trades)*100:.1f}% |")

    # Walk-forward: 5 folds
    lines += ["", "## Walk-forward (5 окон)", "",
              "| fold | period | n | win% | mean_net | total | DD |",
              "|---|---|---|---|---|---|---|"]
    sorted_t = trades.sort_values("entry_ts")
    nT = len(sorted_t)
    for i in range(5):
        a, b = i*nT//5, (i+1)*nT//5
        sub = sorted_t.iloc[a:b]
        m = metrics(sub)
        if not m: continue
        p0 = sub.iloc[0]["entry_ts"].date()
        p1 = sub.iloc[-1]["entry_ts"].date()
        lines.append(f"| {i} | {p0} → {p1} | {m['n_trades']} | "
                     f"{m['win_rate']*100:.1f}% | {m['mean_ret']*100:.2f}% | "
                     f"{m['total_ret']*100:.1f}% | {m['max_dd']*100:.1f}% |")

    # Plots
    plot_equity(trades, "All trades — equity curve", "eq_all.png")
    for ft in ["impulse","flat","triangle","double_corr"]:
        sub = trades[trades["fig_type"]==ft]
        if len(sub) > 30:
            plot_equity(sub, f"{ft} — equity curve", f"eq_{ft}.png")
    for itv in trades["interval"].unique():
        sub = trades[trades["interval"]==itv]
        if len(sub) > 30:
            plot_equity(sub, f"{itv} — equity curve", f"eq_{itv}.png")

    lines += ["", "## Графики", "",
              "![All](screenshots/sprint6/eq_all.png)",
              "![Impulse](screenshots/sprint6/eq_impulse.png)",
              "![Flat](screenshots/sprint6/eq_flat.png)",
              "![Triangle](screenshots/sprint6/eq_triangle.png)",
              "![1h](screenshots/sprint6/eq_1h.png)",
              "![1d](screenshots/sprint6/eq_1d.png)"]

    with open(REPORT, "w") as f:
        f.write("\n".join(lines))
    print(f"\nReport: {REPORT}")
    print(f"Equity images: {OUT_DIR}")


if __name__ == "__main__":
    main()
