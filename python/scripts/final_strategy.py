"""Final strategy combo: Flat + Double Correction, fade only.

Loads trades_sprint6.parquet (already filtered to with_htf=True), but we
re-simulate from scratch with chosen exit modes per type:
  - Double Correction: bars=50, TP/SL
  - Flat: bars=20, TP/SL
  - Skip impulse and triangle entirely

Also drop with_htf restriction since we found HTF filter has weak effect
after look-ahead fix — test both versions.
"""
from __future__ import annotations
import sys, os, warnings
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt

from ewb.monowaves import detect_monowaves
from ewb.rules import classify_pivots
from ewb.figures import match_figures
from ewb.htf import htf_bias_series


REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_DIR = os.path.join(REPO, "docs", "validation", "screenshots", "sprint6")
REPORT  = os.path.join(REPO, "docs", "validation", "sprint6-final.md")


SP500 = ["AAPL","MSFT","GOOGL","AMZN","NVDA","META","TSLA","BRK-B","JPM","V",
         "UNH","XOM","JNJ","WMT","MA","PG","HD","LLY","ABBV","KO",
         "PEP","MRK","CVX","AVGO","ORCL","CSCO","NFLX","CRM","AMD","INTC"]
ETFS = ["SPY","QQQ","IWM","DIA","GLD","SLV","USO","TLT","XLF","XLE"]
CRYPTO = ["BTC-USD","ETH-USD","SOL-USD","BNB-USD","XRP-USD","ADA-USD","AVAX-USD","DOGE-USD"]
FOREX = ["EURUSD=X","GBPUSD=X","USDJPY=X","AUDUSD=X","USDCAD=X"]
COMMODS = ["GC=F","SI=F","CL=F","NG=F","HG=F"]
SYMBOLS = SP500 + ETFS + CRYPTO + FOREX + COMMODS
INTERVALS = [("1d","1W","5y"), ("1h","1D","730d")]


def cost_for(ticker):
    if ticker.endswith("-USD") or ticker.endswith("=X") or ticker.endswith("=F"):
        return 0.0013
    return 0.0008


def download(ticker, interval, period):
    try:
        df = yf.download(ticker, period=period, interval=interval,
                         progress=False, auto_adjust=True, threads=False)
    except Exception: return None
    if df is None or df.empty: return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df.columns = [c.lower() for c in df.columns]
    df = df[[c for c in ["open","high","low","close"] if c in df.columns]].dropna()
    return df if len(df) > 100 else None


def simulate_one(df, figs, bias, ticker, interval, require_with_htf=False):
    """Per-type exit configuration:
      - flat: 20 bars, TP/SL
      - double_corr: 50 bars, TP/SL
      - skip impulse, triangle
    """
    close = df["close"].to_numpy()
    high  = df["high"].to_numpy()
    low   = df["low"].to_numpy()
    n = len(close)
    cost = cost_for(ticker)
    trades = []

    config = {
        "flat":        (20, True),
        "double_corr": (50, True),
    }

    for f in figs:
        if f.type not in config: continue
        exit_bars, use_tp_sl = config[f.type]
        entry_idx = f.pivots[-1].confirmation_idx
        if entry_idx < 0: entry_idx = f.end_idx
        if entry_idx + exit_bars >= n: continue
        bias_val = int(bias.iloc[entry_idx]) if entry_idx < len(bias) else 0
        with_htf = (f.direction == "up" and bias_val > 0) or \
                   (f.direction == "down" and bias_val < 0)
        if require_with_htf and not with_htf: continue
        entry_px = close[entry_idx]
        if entry_px <= 0 or np.isnan(entry_px): continue

        side = -1 if f.direction == "up" else +1   # FADE
        amp = f.amplitude
        if amp <= 0: continue

        if use_tp_sl:
            if side == +1:
                tp_px = entry_px + amp
                sl_px = entry_px - amp
            else:
                tp_px = entry_px - amp
                sl_px = entry_px + amp
        else:
            tp_px = sl_px = None

        exit_idx, exit_px, reason = None, None, "time"
        for k in range(1, exit_bars + 1):
            bi = entry_idx + k
            if bi >= n: break
            hi, lo = high[bi], low[bi]
            if tp_px is not None:
                if side == +1:
                    if lo <= sl_px: exit_idx, exit_px, reason = bi, sl_px, "sl"; break
                    if hi >= tp_px: exit_idx, exit_px, reason = bi, tp_px, "tp"; break
                else:
                    if hi >= sl_px: exit_idx, exit_px, reason = bi, sl_px, "sl"; break
                    if lo <= tp_px: exit_idx, exit_px, reason = bi, tp_px, "tp"; break
        if exit_idx is None:
            exit_idx = entry_idx + exit_bars
            exit_px = close[exit_idx]

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
            "amp_pct": amp / entry_px,
            "raw_ret": raw, "net_ret": net,
            "win": net > 0, "exit_reason": reason,
        })
    return trades


def simulate_all(require_with_htf=False):
    all_trades = []
    for ticker in SYMBOLS:
        for (interval, htf_rule, period) in INTERVALS:
            df = download(ticker, interval, period)
            if df is None: continue
            try:
                p = detect_monowaves(df, atr_mult=2.5)
                classify_pivots(p)
                f = match_figures(p)
                b = htf_bias_series(df, htf_rule)
            except Exception: continue
            all_trades.extend(simulate_one(df, f, b, ticker, interval, require_with_htf))
    return pd.DataFrame(all_trades)


def portfolio(trades, risk=0.01, max_conc=10, initial=100_000):
    if trades.empty: return None
    t = trades.copy()
    t["entry_ts"] = pd.to_datetime(t["entry_ts"], utc=True)
    t["exit_ts"]  = pd.to_datetime(t["exit_ts"], utc=True)
    t = t.sort_values("entry_ts").reset_index(drop=True)
    eq = initial
    open_pos = []
    curve = []
    for _, row in t.iterrows():
        open_pos.sort(key=lambda x: x[0])
        while open_pos and open_pos[0][0] <= row["entry_ts"]:
            ts, pnl = open_pos.pop(0); eq += pnl
            curve.append({"ts": ts, "eq": eq})
        if len(open_pos) >= max_conc: continue
        sl_dist = max(row["amp_pct"], 0.005)
        size = min(eq * risk / sl_dist, eq * 0.5)
        open_pos.append((row["exit_ts"], size * row["net_ret"]))
        curve.append({"ts": row["entry_ts"], "eq": eq})
    for ts, pnl in sorted(open_pos):
        eq += pnl
        curve.append({"ts": ts, "eq": eq})
    df_eq = pd.DataFrame(curve).sort_values("ts")
    df_eq["ts"] = pd.to_datetime(df_eq["ts"], utc=True)
    final = df_eq["eq"].iloc[-1]
    peak = df_eq["eq"].cummax()
    dd = (df_eq["eq"]/peak - 1).min()
    daily = df_eq.set_index("ts").sort_index()["eq"].resample("1D").last().ffill()
    dret = daily.pct_change().dropna()
    yrs = (daily.index[-1] - daily.index[0]).days/365.25
    cagr = (final/initial)**(1/yrs)-1 if yrs>0 else 0
    sharpe = dret.mean()/dret.std()*np.sqrt(252) if dret.std()>0 else 0
    return {
        "n": len(t), "final": final, "total_pct": (final/initial-1)*100,
        "cagr_pct": cagr*100, "sharpe": sharpe, "dd_pct": dd*100,
        "calmar": cagr/abs(dd) if dd != 0 else 0,
        "win_rate": (t["net_ret"]>0).mean()*100,
        "avg_win":  t.loc[t["net_ret"]>0, "net_ret"].mean()*100 if (t["net_ret"]>0).any() else 0,
        "avg_loss": t.loc[t["net_ret"]<=0, "net_ret"].mean()*100 if (t["net_ret"]<=0).any() else 0,
        "yrs": yrs,
        "eq_curve": df_eq,
    }


def plot_eq(m, title, fname):
    if not m: return
    eq = m["eq_curve"]
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True,
                             gridspec_kw={"height_ratios":[3,1]})
    axes[0].plot(eq["ts"], eq["eq"], color="#22cc77", linewidth=1.4)
    axes[0].axhline(100000, color="white", lw=0.7, ls="--", alpha=0.4)
    sub_title = (f"{title}\nCAGR={m['cagr_pct']:.1f}%  Sharpe={m['sharpe']:.2f}  "
                 f"DD={m['dd_pct']:.1f}%  Calmar={m['calmar']:.2f}  n={m['n']}  win={m['win_rate']:.1f}%")
    axes[0].set_title(sub_title, color="#ddd")
    axes[0].set_ylabel("equity $", color="#aaa")
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
    plt.savefig(os.path.join(OUT_DIR, fname), dpi=110, facecolor=fig.get_facecolor())
    plt.close(fig)


def walk_forward(trades, n_folds=5):
    if trades.empty: return []
    t = trades.copy()
    t["entry_ts"] = pd.to_datetime(t["entry_ts"], utc=True)
    t = t.sort_values("entry_ts").reset_index(drop=True)
    nT = len(t)
    rows = []
    for i in range(n_folds):
        a, b = i*nT//n_folds, (i+1)*nT//n_folds
        sub = t.iloc[a:b]
        m = portfolio(sub)
        if m:
            rows.append({
                "fold": i,
                "period": f"{sub.iloc[0]['entry_ts'].date()} → {sub.iloc[-1]['entry_ts'].date()}",
                "n": m["n"], "cagr": m["cagr_pct"],
                "sharpe": m["sharpe"], "dd": m["dd_pct"],
                "win": m["win_rate"],
            })
    return rows


def main():
    print("Simulating combined strategy (Flat + DC, fade, per-type config)...")
    print(" Variant A: no HTF requirement")
    trades_a = simulate_all(require_with_htf=False)
    print(f"  trades: {len(trades_a)}")
    print(" Variant B: with HTF requirement")
    trades_b = simulate_all(require_with_htf=True)
    print(f"  trades: {len(trades_b)}")

    m_a = portfolio(trades_a)
    m_b = portfolio(trades_b)

    lines = [
        "# Спринт 6.7 — Final combined strategy",
        "",
        f"**Дата:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Стратегия",
        "",
        "- **Flat**: fade direction, exit 20 баров или TP/SL (TP=полный ретрейс, SL=амплитуда фигуры)",
        "- **Double Correction**: fade direction, exit 50 баров или TP/SL",
        "- **Impulse, Triangle**: НЕ торгуем (shown as noise in Sprint 6.5)",
        "",
        "## Вариант A: без HTF фильтра",
        "",
    ]
    if m_a:
        lines += [f"- **n_trades:** {m_a['n']} за {m_a['yrs']:.1f} лет",
                  f"- **Final:** ${m_a['final']:,.0f} (start $100k)",
                  f"- **CAGR:** {m_a['cagr_pct']:.1f}%",
                  f"- **Sharpe:** {m_a['sharpe']:.2f}",
                  f"- **Max DD:** {m_a['dd_pct']:.1f}%",
                  f"- **Calmar:** {m_a['calmar']:.2f}",
                  f"- **Win rate:** {m_a['win_rate']:.1f}%",
                  f"- **Avg win / loss:** +{m_a['avg_win']:.2f}% / {m_a['avg_loss']:.2f}%",
                  ""]
        plot_eq(m_a, "Final combo: Flat+DC fade — no HTF filter", "final_noHTF.png")
        lines.append("![A](screenshots/sprint6/final_noHTF.png)")
        lines.append("")

    lines += ["## Вариант B: только with_htf=True", ""]
    if m_b:
        lines += [f"- **n_trades:** {m_b['n']} за {m_b['yrs']:.1f} лет",
                  f"- **Final:** ${m_b['final']:,.0f}",
                  f"- **CAGR:** {m_b['cagr_pct']:.1f}%",
                  f"- **Sharpe:** {m_b['sharpe']:.2f}",
                  f"- **Max DD:** {m_b['dd_pct']:.1f}%",
                  f"- **Calmar:** {m_b['calmar']:.2f}",
                  f"- **Win rate:** {m_b['win_rate']:.1f}%",
                  ""]
        plot_eq(m_b, "Final combo: Flat+DC fade — HTF filter", "final_withHTF.png")
        lines.append("![B](screenshots/sprint6/final_withHTF.png)")
        lines.append("")

    # Walk-forward of Variant A
    lines += ["## Walk-forward 5 окон (вариант A)", "",
              "| fold | period | n | CAGR | Sharpe | DD | win |",
              "|---|---|---|---|---|---|---|"]
    for r in walk_forward(trades_a, 5):
        lines.append(f"| {r['fold']} | {r['period']} | {r['n']} | "
                     f"{r['cagr']:.1f}% | {r['sharpe']:.2f} | {r['dd']:.1f}% | {r['win']:.1f}% |")
    lines += [""]

    # Per fig type breakdown
    lines += ["## По типу фигуры (вариант A)", "",
              "| type | n | CAGR | Sharpe | DD | win |",
              "|---|---|---|---|---|---|"]
    for ft in ["flat","double_corr"]:
        sub = trades_a[trades_a["fig_type"]==ft]
        if len(sub)<10: continue
        m = portfolio(sub)
        if m:
            lines.append(f"| {ft} | {m['n']} | {m['cagr_pct']:.1f}% | "
                         f"{m['sharpe']:.2f} | {m['dd_pct']:.1f}% | {m['win_rate']:.1f}% |")

    # Per interval
    lines += ["", "## По таймфрейму (вариант A)", "",
              "| interval | n | CAGR | Sharpe | DD |",
              "|---|---|---|---|---|"]
    for itv in sorted(trades_a["interval"].unique()):
        sub = trades_a[trades_a["interval"]==itv]
        m = portfolio(sub)
        if m:
            lines.append(f"| {itv} | {m['n']} | {m['cagr_pct']:.1f}% | "
                         f"{m['sharpe']:.2f} | {m['dd_pct']:.1f}% |")

    with open(REPORT, "w") as f:
        f.write("\n".join(lines))
    print(f"\nReport: {REPORT}")
    print(f"\nVariant A: {m_a['cagr_pct']:.1f}% CAGR, Sharpe {m_a['sharpe']:.2f}, DD {m_a['dd_pct']:.1f}%")
    if m_b:
        print(f"Variant B: {m_b['cagr_pct']:.1f}% CAGR, Sharpe {m_b['sharpe']:.2f}, DD {m_b['dd_pct']:.1f}%")


if __name__ == "__main__":
    main()
