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
import yfinance as yf
import matplotlib.pyplot as plt

from ewb.monowaves import detect_monowaves
from ewb.rules import classify_pivots
from ewb.figures import match_figures
from ewb.htf import htf_bias_series


REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_DIR = os.path.join(REPO, "docs", "validation", "screenshots", "sprint6")
REPORT  = os.path.join(REPO, "docs", "validation", "sprint6-variants.md")
os.makedirs(OUT_DIR, exist_ok=True)


def cost_for(ticker):
    if ticker.endswith("-USD") or ticker.endswith("=X") or ticker.endswith("=F"):
        return 0.0013
    return 0.0008


SP500 = ["AAPL","MSFT","GOOGL","AMZN","NVDA","META","TSLA","BRK-B","JPM","V",
         "UNH","XOM","JNJ","WMT","MA","PG","HD","LLY","ABBV","KO",
         "PEP","MRK","CVX","AVGO","ORCL","CSCO","NFLX","CRM","AMD","INTC"]
ETFS = ["SPY","QQQ","IWM","DIA","GLD","SLV","USO","TLT","XLF","XLE"]
CRYPTO = ["BTC-USD","ETH-USD","SOL-USD","BNB-USD","XRP-USD","ADA-USD","AVAX-USD","DOGE-USD"]
FOREX = ["EURUSD=X","GBPUSD=X","USDJPY=X","AUDUSD=X","USDCAD=X"]
COMMODS = ["GC=F","SI=F","CL=F","NG=F","HG=F"]
SYMBOLS = SP500 + ETFS + CRYPTO + FOREX + COMMODS
INTERVALS = [("1d","1W","5y"), ("1h","1D","730d")]


def download(ticker, interval, period):
    try:
        df = yf.download(ticker, period=period, interval=interval,
                         progress=False, auto_adjust=True, threads=False)
    except Exception:
        return None
    if df is None or df.empty: return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df.columns = [c.lower() for c in df.columns]
    df = df[[c for c in ["open","high","low","close"] if c in df.columns]].dropna()
    return df if len(df) > 100 else None


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
        if use_tp_sl and amp > 0:
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
                    if lo <= sl_px:
                        exit_idx, exit_px, reason = bi, sl_px, "sl"; break
                    if hi >= tp_px:
                        exit_idx, exit_px, reason = bi, tp_px, "tp"; break
                else:
                    if hi >= sl_px:
                        exit_idx, exit_px, reason = bi, sl_px, "sl"; break
                    if lo <= tp_px:
                        exit_idx, exit_px, reason = bi, tp_px, "tp"; break
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
            df = download(ticker, interval, period)
            if df is None: continue
            try:
                p = detect_monowaves(df, atr_mult=2.5)
                classify_pivots(p)
                f = match_figures(p)
                b = htf_bias_series(df, htf_rule)
            except Exception:
                continue
            all_trades.extend(simulate_one(df, f, b, ticker, interval,
                                           strategy, exit_bars, use_tp_sl))
    return pd.DataFrame(all_trades)


def portfolio_metrics(trades, risk=0.01, max_conc=10, initial=100_000):
    if trades.empty: return None
    t = trades.copy()
    t["entry_ts"] = pd.to_datetime(t["entry_ts"], utc=True)
    t["exit_ts"]  = pd.to_datetime(t["exit_ts"], utc=True)
    t = t.sort_values("entry_ts").reset_index(drop=True)
    eq = initial
    open_pos = []
    curve = []
    skipped = 0
    for _, row in t.iterrows():
        open_pos.sort(key=lambda x: x[0])
        while open_pos and open_pos[0][0] <= row["entry_ts"]:
            ts, pnl = open_pos.pop(0)
            eq += pnl
            curve.append({"ts": ts, "eq": eq})
        if len(open_pos) >= max_conc: skipped += 1; continue
        sl_dist = max(row["amp_pct"] or 0, 0.005)  # min 0.5% to avoid huge sizes
        size = min(eq * risk / sl_dist, eq * 0.5)
        pnl = size * row["net_ret"]
        open_pos.append((row["exit_ts"], pnl))
        curve.append({"ts": row["entry_ts"], "eq": eq})
    for ts, pnl in sorted(open_pos):
        eq += pnl
        curve.append({"ts": ts, "eq": eq})
    df_eq = pd.DataFrame(curve).sort_values("ts")
    if df_eq.empty: return None
    final = df_eq["eq"].iloc[-1]
    peak = df_eq["eq"].cummax()
    dd = (df_eq["eq"]/peak - 1).min()
    df_eq["ts"] = pd.to_datetime(df_eq["ts"], utc=True)
    daily = df_eq.set_index("ts").sort_index()["eq"].resample("1D").last().ffill()
    daily_ret = daily.pct_change().dropna()
    years = (daily.index[-1] - daily.index[0]).days / 365.25
    cagr = (final/initial)**(1/years) - 1 if years > 0 else 0
    sharpe = daily_ret.mean()/daily_ret.std()*np.sqrt(252) if daily_ret.std()>0 else 0
    return {
        "n": len(t)-skipped, "final": final,
        "total_pct": (final/initial-1)*100,
        "cagr": cagr*100, "sharpe": sharpe,
        "max_dd": dd*100,
        "calmar": cagr/abs(dd) if dd!=0 else 0,
        "win_rate": (t["net_ret"]>0).mean()*100,
        "eq_curve": df_eq,
    }


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
                "n": m_all["n"], "cagr": m_all["cagr"],
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
                    "n": m["n"], "cagr": m["cagr"],
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
