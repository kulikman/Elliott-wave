"""Backtest final strategy (Flat+DC fade) across all TFs.

Simulates trades on all 6 TFs × 58 symbols, then combines into one portfolio.
Per-TF results + combined equity curve.
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
from ewb.htf import htf_bias_series, resample_ohlc
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
REPORT  = os.path.join(REPO, "docs", "validation", "sprint6-all-tfs-bt.md")
os.makedirs(OUT_DIR, exist_ok=True)

ALL_INTERVALS = [
    ("1wk","1ME","10y","1w"),
    ("1h", "1D","730d","4h"),   # will resample 1h→4h
    ("1d", "1W", "5y","1d"),
    ("1h", "1D","730d","1h"),
    ("30m","1h","60d","30m"),
    ("15m","1h","60d","15m"),
]

FIG_CONFIG = {
    "flat":        {"exit_bars": 20, "use_tp_sl": True},
    "double_corr": {"exit_bars": 50, "use_tp_sl": True},
}

def simulate_ticker(df_ctf, figs, bias, ticker, interval_label, cost):
    close = df_ctf["close"].to_numpy()
    high  = df_ctf["high"].to_numpy()
    low   = df_ctf["low"].to_numpy()
    n = len(close)
    trades = []
    for f in figs:
        if not f.confirmed:
            continue
        if f.type not in FIG_CONFIG: continue
        cfg = FIG_CONFIG[f.type]
        exit_bars = cfg["exit_bars"]
        use_tp_sl = cfg["use_tp_sl"]
        entry_idx = f.pivots[-1].confirmation_idx
        if entry_idx < 0: entry_idx = f.end_idx
        if entry_idx + exit_bars >= n: continue
        entry_px = close[entry_idx]
        if entry_px <= 0 or np.isnan(entry_px): continue
        amp = f.amplitude
        if amp <= 0: continue
        side = -1 if f.direction == "up" else +1
        exit_idx, exit_px, reason = exit_for_trade(
            high, low, close, entry_idx, entry_px, side, exit_bars, amp, use_tp_sl
        )
        raw = side * (exit_px - entry_px) / entry_px
        net = raw - 2 * cost
        trades.append({
            "ticker": ticker, "interval": interval_label,
            "fig_type": f.type,
            "entry_ts": df_ctf.index[entry_idx],
            "exit_ts":  df_ctf.index[exit_idx],
            "amp_pct": amp / entry_px,
            "raw_ret": raw, "net_ret": net,
            "win": net > 0,
        })
    return trades

def plot_combined(all_trades, per_tf_metrics, fname):
    fig, axes = plt.subplots(2, 1, figsize=(16, 9), sharex=True,
                             gridspec_kw={"height_ratios":[3,1]})
    colors = {"1w":"#ff9020","4h":"#22cc77","1d":"#4488ff","1h":"#cc44cc",
              "30m":"#ff4444","15m":"#ffdd00"}
    for lbl, m in per_tf_metrics.items():
        if not m: continue
        eq = m["curve"]
        axes[0].plot(eq["ts"], eq["eq"], color=colors.get(lbl,"#aaa"),
                     linewidth=1.0, alpha=0.6, label=f"{lbl} ({m['cagr']*100:.0f}% CAGR)")
    # Combined
    if all_trades:
        m = portfolio_metrics(all_trades)
        if m:
            axes[0].plot(m["curve"]["ts"], m["curve"]["eq"],
                         color="white", linewidth=2.0, label=f"COMBINED ({m['cagr']*100:.0f}% CAGR Sh={m['sharpe']:.2f})")
            peak = m["curve"]["eq"].cummax()
            dd = (m["curve"]["eq"]/peak-1)*100
            axes[1].fill_between(m["curve"]["ts"], dd, 0, color="#cc3344", alpha=0.6)
    axes[0].axhline(100_000, color="white", lw=0.7, ls="--", alpha=0.4)
    axes[0].set_title("Flat+DC fade — all TFs portfolio", color="#ddd")
    axes[0].set_ylabel("equity $", color="#aaa")
    axes[0].legend(loc="upper left", fontsize=8)
    axes[0].set_facecolor("#0e0e10"); axes[0].tick_params(colors="#aaa")
    for s in axes[0].spines.values(): s.set_color("#444")
    axes[1].set_ylabel("DD %", color="#aaa")
    axes[1].set_facecolor("#0e0e10"); axes[1].tick_params(colors="#aaa")
    for s in axes[1].spines.values(): s.set_color("#444")
    fig.patch.set_facecolor("#1a1a1d")
    plt.tight_layout()
    plt.savefig(fname, dpi=110, facecolor=fig.get_facecolor())
    plt.close(fig)


def main():
    t0 = time.time()
    all_trades = []
    per_tf = {lbl: [] for _, _, _, lbl in ALL_INTERVALS}
    done = 0
    total = len(SYMBOLS) * len(ALL_INTERVALS)

    downloaded_1h = {}   # cache 1h downloads to reuse for 4h

    for ticker in SYMBOLS:
        for (yf_interval, htf_rule, period, label) in ALL_INTERVALS:
            done += 1
            cost = cost_for(ticker)

            if label == "4h":
                df_raw = downloaded_1h.get(ticker)
                if df_raw is None:
                    df_raw = download_ohlc(ticker, "1h", "730d")
                    downloaded_1h[ticker] = df_raw
                df_ctf = resample_ohlc(df_raw, "4h") if df_raw is not None else None
            else:
                if label == "1h":
                    df_raw = download_ohlc(ticker, yf_interval, period)
                    downloaded_1h[ticker] = df_raw  # cache for 4h
                    df_ctf = df_raw
                else:
                    df_ctf = download_ohlc(ticker, yf_interval, period)

            if df_ctf is None or len(df_ctf) < 50: continue

            try:
                pivots = detect_monowaves(df_ctf, atr_mult=2.5)
                classify_pivots(pivots)
                figs = match_figures(pivots)
                bias = htf_bias_series(df_ctf, htf_rule)
            except Exception as exc:
                log_processing_error(ticker, label, exc)
                continue

            trades = simulate_ticker(df_ctf, figs, bias, ticker, label, cost)
            per_tf[label].extend(trades)
            all_trades.extend(trades)
            elapsed = time.time()-t0
            eta = elapsed/done*(total-done)
            print(f"[{done:3}/{total}] {ticker:10} {label:3}  trades={len(trades):3}  "
                  f"total={len(all_trades):5}  {elapsed:.0f}s eta={eta:.0f}s")

    # Metrics per TF
    per_tf_metrics = {}
    lines = ["# Backtest: Flat+DC fade — все таймфреймы",
             "",
             f"**Дата:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}",
             f"**Всего сделок:** {len(all_trades)}",
             "",
             "## По таймфреймам", "",
             "| TF | n | Final$ | CAGR | Sharpe | DD | Calmar | Win |",
             "|---|---|---|---|---|---|---|---|"]

    for lbl in ["1w","4h","1d","1h","30m","15m"]:
        m = portfolio_metrics(per_tf[lbl])
        per_tf_metrics[lbl] = m
        if not m: continue
        lines.append(f"| {lbl} | {m['n']} | ${m['final']:,.0f} | "
                     f"{m['cagr']*100:.1f}% | {m['sharpe']:.2f} | "
                     f"{m['dd']*100:.1f}% | {m['calmar']:.2f} | {m['win']*100:.1f}% |")

    # Combined
    m_all = portfolio_metrics(all_trades)
    lines += ["", "## Комбинированный портфель (все ТФ)", ""]
    if m_all:
        lines += [
            f"- **Сделок:** {m_all['n']} за {m_all['yrs']:.1f} лет",
            f"- **Final:** ${m_all['final']:,.0f}  (start $100k)",
            f"- **CAGR:** {m_all['cagr']*100:.1f}%",
            f"- **Sharpe:** {m_all['sharpe']:.2f}",
            f"- **Max DD:** {m_all['dd']*100:.1f}%",
            f"- **Calmar:** {m_all['calmar']:.2f}",
            f"- **Win rate:** {m_all['win']*100:.1f}%",
            "",
            "![Combined](screenshots/sprint6/all_tfs_combined.png)",
        ]

    # Walk-forward combined
    if all_trades:
        t_df = pd.DataFrame(all_trades)
        t_df["entry_ts"] = pd.to_datetime(t_df["entry_ts"], utc=True)
        t_df = t_df.sort_values("entry_ts").reset_index(drop=True)
        n = len(t_df)
        lines += ["", "## Walk-forward 5 окон", "",
                  "| fold | period | n | CAGR | Sharpe | DD |",
                  "|---|---|---|---|---|---|"]
        for i in range(5):
            sub = t_df.iloc[i*n//5:(i+1)*n//5]
            m = portfolio_metrics(sub.to_dict("records"))
            if not m: continue
            p0 = sub.iloc[0]["entry_ts"].date()
            p1 = sub.iloc[-1]["entry_ts"].date()
            lines.append(f"| {i} | {p0}→{p1} | {m['n']} | "
                         f"{m['cagr']*100:.1f}% | {m['sharpe']:.2f} | {m['dd']*100:.1f}% |")

    # Plot
    plot_combined(all_trades, per_tf_metrics,
                  os.path.join(OUT_DIR, "all_tfs_combined.png"))

    with open(REPORT, "w") as f:
        f.write("\n".join(lines))
    print(f"\nReport: {REPORT}")
    if m_all:
        print(f"Combined: CAGR={m_all['cagr']*100:.1f}% Sharpe={m_all['sharpe']:.2f} DD={m_all['dd']*100:.1f}%")


if __name__ == "__main__":
    main()
