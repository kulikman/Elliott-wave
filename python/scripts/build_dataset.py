"""Sprint 3 — Build wide dataset.

50+ symbols × 3 timeframes → parquet of figures with features + future returns.
Used as input for Sprint 4-extended edge stats and Sprint 5 ML.
"""
from __future__ import annotations
import sys, os, warnings, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import yfinance as yf

from ewb.monowaves import detect_monowaves
from ewb.rules import classify_pivots
from ewb.figures import match_figures
from ewb.htf import htf_bias_series


REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_PARQUET = os.path.join(REPO, "python", "data", "figures_wide.parquet")
os.makedirs(os.path.dirname(OUT_PARQUET), exist_ok=True)


# ─── UNIVERSE ────────────────────────────────────────────────
SP500_TOP = [
    "AAPL","MSFT","GOOGL","AMZN","NVDA","META","TSLA","BRK-B","JPM","V",
    "UNH","XOM","JNJ","WMT","MA","PG","HD","LLY","ABBV","KO",
    "PEP","MRK","CVX","AVGO","ORCL","CSCO","NFLX","CRM","AMD","INTC",
]
ETFS = ["SPY","QQQ","IWM","DIA","GLD","SLV","USO","TLT","XLF","XLE"]
CRYPTO = ["BTC-USD","ETH-USD","SOL-USD","BNB-USD","XRP-USD","ADA-USD","AVAX-USD","DOGE-USD"]
FOREX = ["EURUSD=X","GBPUSD=X","USDJPY=X","AUDUSD=X","USDCAD=X"]
COMMODITIES = ["GC=F","SI=F","CL=F","NG=F","HG=F"]

SYMBOLS = SP500_TOP + ETFS + CRYPTO + FOREX + COMMODITIES

# (interval, htf_rule, period) — limited by yfinance:
# 1d: any period | 1h: 730d max | 4h: derived via 1h resample or directly via 4h (also ≤730d) | 15m: 60d max
INTERVALS = [
    ("1d", "1W", "5y"),
    ("1h", "1D", "730d"),
]

HORIZONS = [5, 10, 20, 50, 100]


def download(ticker, interval, period):
    try:
        df = yf.download(ticker, period=period, interval=interval,
                         progress=False, auto_adjust=True, threads=False)
    except Exception as e:
        return None
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df.columns = [c.lower() for c in df.columns]
    cols = [c for c in ["open","high","low","close","volume"] if c in df.columns]
    df = df[cols].dropna()
    return df if len(df) > 50 else None


def figures_to_rows(df, pivots, figs, bias, ticker, interval):
    rows = []
    close = df["close"].to_numpy()
    n = len(close)
    for f in figs:
        entry_idx = f.pivots[-1].confirmation_idx
        if entry_idx < 0:
            entry_idx = f.end_idx
        if entry_idx >= n - max(HORIZONS):
            continue
        entry_px = close[entry_idx]
        if entry_px <= 0 or np.isnan(entry_px):
            continue

        bias_val = int(bias.iloc[entry_idx]) if entry_idx < len(bias) else 0
        with_htf = (f.direction == "up" and bias_val > 0) or \
                   (f.direction == "down" and bias_val < 0)
        against_htf = (f.direction == "up" and bias_val < 0) or \
                      (f.direction == "down" and bias_val > 0)

        # Wave length features (5 lengths for impulse, 4 for triangle, 3 for flat/zigzag/dc)
        ws = [abs(f.pivots[i+1].price - f.pivots[i].price) for i in range(len(f.pivots)-1)]
        ts = [f.pivots[i+1].idx - f.pivots[i].idx for i in range(len(f.pivots)-1)]

        row = {
            "ticker": ticker, "interval": interval,
            "end_ts": df.index[f.end_idx],
            "entry_ts": df.index[entry_idx],
            "confirmation_lag": entry_idx - f.end_idx,
            "fig_type": f.type, "direction": f.direction,
            "confirmed": f.confirmed,
            "duration": f.duration,
            "amplitude": f.amplitude,
            "amp_pct": f.amplitude / entry_px,
            "htf_bias": bias_val,
            "with_htf": with_htf,
            "against_htf": against_htf,
            "n_pivots": len(f.pivots),
            "n_errors": sum(1 for c in f.checks if c.severity=="E" and not c.ok),
            "n_warnings": sum(1 for c in f.checks if c.severity=="W" and not c.ok),
            "entry_px": entry_px,
            # wave length ratios
            "w1_w2_ratio": (ws[0]/ws[1]) if len(ws)>=2 and ws[1]>0 else np.nan,
            "w3_w1_ratio": (ws[2]/ws[0]) if len(ws)>=3 and ws[0]>0 else np.nan,
            "w4_w2_ratio": (ws[3]/ws[1]) if len(ws)>=4 and ws[1]>0 else np.nan,
            "w5_w3_ratio": (ws[4]/ws[2]) if len(ws)>=5 and ws[2]>0 else np.nan,
            "avg_dur_per_wave": np.mean(ts) if ts else np.nan,
        }
        for h in HORIZONS:
            if entry_idx + h < n:
                fut = close[entry_idx + h]
                ret = (fut - entry_px) / entry_px
                row[f"ret_{h}"] = ret
                sign = -1 if f.direction == "up" else +1
                row[f"signed_ret_{h}"] = ret * sign
            else:
                row[f"ret_{h}"] = np.nan
                row[f"signed_ret_{h}"] = np.nan
        rows.append(row)
    return rows


def main():
    all_rows = []
    total = len(SYMBOLS) * len(INTERVALS)
    done = 0
    t0 = time.time()
    skipped = []
    for ticker in SYMBOLS:
        for (interval, htf_rule, period) in INTERVALS:
            done += 1
            df = download(ticker, interval, period)
            if df is None:
                skipped.append(f"{ticker}/{interval}")
                continue
            try:
                pivots = detect_monowaves(df, atr_mult=2.5)
                classify_pivots(pivots)
                figs = match_figures(pivots)
                bias = htf_bias_series(df, htf_rule)
            except Exception as e:
                skipped.append(f"{ticker}/{interval}:{e}")
                continue
            rows = figures_to_rows(df, pivots, figs, bias, ticker, interval)
            all_rows.extend(rows)
            elapsed = time.time() - t0
            eta = elapsed / done * (total - done)
            print(f"[{done:3}/{total}] {ticker:10} {interval:3} → {len(rows):4} rows "
                  f"(bars={len(df)}, figs={len(figs)})  elapsed={elapsed:.0f}s  eta={eta:.0f}s")

    df_out = pd.DataFrame(all_rows)
    df_out.to_parquet(OUT_PARQUET)
    print(f"\n=== DONE ===")
    print(f"Total figures: {len(df_out)}")
    print(f"By type:\n{df_out['fig_type'].value_counts()}")
    print(f"By interval:\n{df_out['interval'].value_counts()}")
    print(f"Saved: {OUT_PARQUET}")
    if skipped:
        print(f"\nSkipped {len(skipped)}: {skipped[:10]}{'...' if len(skipped)>10 else ''}")


if __name__ == "__main__":
    main()
