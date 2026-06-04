"""Sprint 6 portfolio backtest — realistic position sizing.

Loads trades_sprint6.parquet and simulates as a portfolio:
- Fixed risk 1% of equity per trade (sized off SL distance)
- Max 10 concurrent positions
- Skip if at max
- Properly handle overlap across 58 instruments
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
import matplotlib.pyplot as plt

from ewb.research import portfolio_metrics

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TRADES = os.path.join(REPO, "python", "data", "trades_sprint6.parquet")
OUT_DIR = os.path.join(REPO, "docs", "validation", "screenshots", "sprint6")
REPORT  = os.path.join(REPO, "docs", "validation", "sprint6-portfolio.md")


RISK_PER_TRADE = 0.01      # 1% of equity per trade
MAX_CONCURRENT = 10
INITIAL_CAPITAL = 100_000


def portfolio_report(trades: pd.DataFrame) -> dict | None:
    """Portfolio metrics in the legacy report shape."""
    m = portfolio_metrics(
        trades,
        initial=INITIAL_CAPITAL,
        risk=RISK_PER_TRADE,
        max_conc=MAX_CONCURRENT,
        min_sl_dist=0.0,
    )
    if not m:
        return None
    return {
        **m,
        "eq": m["equity_curve"],
        "max_dd": m["dd"],
        "n_trades": m["n"],
    }


def fmt_m(m: dict) -> str:
    return (f"final=${m['final_equity']:,.0f}, total={m['total_return']*100:.1f}%, "
            f"CAGR={m['cagr']*100:.1f}%, Sharpe={m['sharpe']:.2f}, "
            f"DD={m['max_dd']*100:.1f}%, Calmar={m['calmar']:.2f}, "
            f"n={m['n_trades']}, {m['years']:.1f}y")


def plot(eq: pd.DataFrame, title: str, fname: str):
    if eq.empty: return
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True,
                             gridspec_kw={"height_ratios":[3,1]})
    eq_ts = pd.to_datetime(eq["ts"], utc=True)
    axes[0].plot(eq_ts, eq["equity"], color="#22cc77", linewidth=1.3)
    axes[0].axhline(INITIAL_CAPITAL, color="white", lw=0.7, ls="--", alpha=0.4)
    axes[0].set_title(title, color="#ddd")
    axes[0].set_ylabel("equity $", color="#aaa")
    axes[0].set_facecolor("#0e0e10"); axes[0].tick_params(colors="#aaa")
    for s in axes[0].spines.values(): s.set_color("#444")

    peak = eq["equity"].cummax()
    dd = (eq["equity"] / peak - 1) * 100
    axes[1].fill_between(eq_ts, dd, 0, color="#cc3344", alpha=0.6)
    axes[1].set_ylabel("DD %", color="#aaa")
    axes[1].set_facecolor("#0e0e10"); axes[1].tick_params(colors="#aaa")
    for s in axes[1].spines.values(): s.set_color("#444")

    fig.patch.set_facecolor("#1a1a1d")
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, fname), dpi=110, facecolor=fig.get_facecolor())
    plt.close(fig)


def main():
    trades = pd.read_parquet(TRADES)
    trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
    trades["exit_ts"]  = pd.to_datetime(trades["exit_ts"], utc=True)
    print(f"Loaded {len(trades)} trades")

    lines = [
        "# Спринт 6 — Portfolio Backtest",
        "",
        f"**Дата:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Капитал:** ${INITIAL_CAPITAL:,}, **риск/сделка:** {RISK_PER_TRADE*100}%, **max concurrent:** {MAX_CONCURRENT}",
        f"**Сделки из:** trades_sprint6.parquet ({len(trades)} строк)",
        "",
        "Position size sized from SL distance: `size = equity × risk / sl_distance`. ",
        "Stop = entry ± amplitude фигуры. Если бы цена прошла SL — теряем 1% капитала.",
        "",
        "## Полный портфель", "",
    ]
    m_all = portfolio_report(trades)
    if not m_all:
        print("No portfolio metrics — abort")
        return
    lines.append(fmt_m(m_all))
    lines.append(f"\n*Пропущено сделок (превышен лимит {MAX_CONCURRENT} параллельных): {m_all['skipped']}*")
    plot(m_all["eq"], "Full portfolio — 1% risk, max 10 concurrent", "port_all.png")

    # Per fig_type
    lines += ["", "## По типу фигуры", "",
              "| fig_type | n | final | total | CAGR | Sharpe | DD | Calmar |",
              "|---|---|---|---|---|---|---|---|"]
    for ft in ["impulse","flat","triangle","double_corr"]:
        sub = trades[trades["fig_type"]==ft]
        if len(sub) < 30: continue
        m = portfolio_report(sub)
        if not m: continue
        lines.append(f"| {ft} | {m['n_trades']} | ${m['final_equity']:,.0f} | "
                     f"{m['total_return']*100:.1f}% | {m['cagr']*100:.1f}% | "
                     f"{m['sharpe']:.2f} | {m['max_dd']*100:.1f}% | {m['calmar']:.2f} |")
        plot(m["eq"], f"{ft} — portfolio", f"port_{ft}.png")

    # Per interval
    lines += ["", "## По таймфрейму", "",
              "| interval | n | final | total | CAGR | Sharpe | DD |",
              "|---|---|---|---|---|---|---|"]
    for itv in sorted(trades["interval"].unique()):
        sub = trades[trades["interval"]==itv]
        m = portfolio_report(sub)
        if not m: continue
        lines.append(f"| {itv} | {m['n_trades']} | ${m['final_equity']:,.0f} | "
                     f"{m['total_return']*100:.1f}% | {m['cagr']*100:.1f}% | "
                     f"{m['sharpe']:.2f} | {m['max_dd']*100:.1f}% |")
        plot(m["eq"], f"{itv} — portfolio", f"port_{itv}.png")

    # High-confidence subset: impulse + flat + double_corr (skip noisy triangle)
    lines += ["", "## High-confidence subset (impulse + flat + double_corr, без triangle)", ""]
    hc = trades[trades["fig_type"].isin(["impulse","flat","double_corr"])]
    m_hc = portfolio_report(hc)
    if m_hc:
        lines.append(fmt_m(m_hc))
        plot(m_hc["eq"], "High-confidence subset (impulse+flat+DC)", "port_hc.png")

    # Q4 (large) figures only
    lines += ["", "## Large figures only (amp_pct ≥ median)", ""]
    median_amp = trades["amp_pct"].median()
    big = trades[trades["amp_pct"] >= median_amp]
    m_big = portfolio_report(big)
    if m_big:
        lines.append(fmt_m(m_big))
        plot(m_big["eq"], "Large figures (amp ≥ median)", "port_large.png")

    lines += ["", "## Графики", "",
              "![All](screenshots/sprint6/port_all.png)",
              "![HC](screenshots/sprint6/port_hc.png)",
              "![Large](screenshots/sprint6/port_large.png)",
              "![Impulse](screenshots/sprint6/port_impulse.png)",
              "![Flat](screenshots/sprint6/port_flat.png)",
              "![Triangle](screenshots/sprint6/port_triangle.png)",
              "![1h](screenshots/sprint6/port_1h.png)",
              "![1d](screenshots/sprint6/port_1d.png)"]

    with open(REPORT, "w") as f:
        f.write("\n".join(lines))
    print(f"Report: {REPORT}")
    print(f"\nFull portfolio: {fmt_m(m_all)}")


if __name__ == "__main__":
    main()
