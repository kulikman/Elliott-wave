"""Add 1w / 4h / 30m / 15m timeframes to figures dataset.

yfinance limits:
  1wk  → any period  (use 10y)
  1h   → 730d        (resample → 4h with pandas)
  30m  → 60d
  15m  → 60d

HTF pairing:
  15m  → 1h  HTF
  30m  → 4h  HTF (derived)
  4h   → 1D  HTF (pandas 'D')
  1w   → 1ME HTF (month-end)

Output: appends to figures_wide.parquet (or writes figures_all_tfs.parquet)
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
from ewb.htf import htf_bias_series, resample_ohlc


REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OLD_PARQUET = os.path.join(REPO, "python", "data", "figures_wide.parquet")
OUT_PARQUET = os.path.join(REPO, "python", "data", "figures_all_tfs.parquet")

SP500 = ["AAPL","MSFT","GOOGL","AMZN","NVDA","META","TSLA","BRK-B","JPM","V",
         "UNH","XOM","JNJ","WMT","MA","PG","HD","LLY","ABBV","KO",
         "PEP","MRK","CVX","AVGO","ORCL","CSCO","NFLX","CRM","AMD","INTC"]
ETFS = ["SPY","QQQ","IWM","DIA","GLD","SLV","USO","TLT","XLF","XLE"]
CRYPTO = ["BTC-USD","ETH-USD","SOL-USD","BNB-USD","XRP-USD","ADA-USD","AVAX-USD","DOGE-USD"]
FOREX = ["EURUSD=X","GBPUSD=X","USDJPY=X","AUDUSD=X","USDCAD=X"]
COMMODS = ["GC=F","SI=F","CL=F","NG=F","HG=F"]
SYMBOLS = SP500 + ETFS + CRYPTO + FOREX + COMMODS

HORIZONS = [5, 10, 20, 50, 100]

# (yf_interval, pandas_htf_rule, yf_period, label)
EXTRA_INTERVALS = [
    ("1wk",  "1ME",  "10y",  "1w"),
    ("1h",   "1D",   "730d", "4h"),   # resample 1h→4h
    ("30m",  "1h",   "60d",  "30m"),
    ("15m",  "1h",   "60d",  "15m"),
]


def download_raw(ticker, yf_interval, period):
    try:
        df = yf.download(ticker, period=period, interval=yf_interval,
                         progress=False, auto_adjust=True, threads=False)
    except Exception:
        return None
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df.columns = [c.lower() for c in df.columns]
    df = df[[c for c in ["open","high","low","close"] if c in df.columns]].dropna()
    return df if len(df) > 50 else None


def prepare_ctf(df_raw, label):
    """Resample if needed (1h→4h), return ctf DataFrame."""
    if label == "4h":
        return resample_ohlc(df_raw, "4h")
    return df_raw


def figures_to_rows(df_ctf, pivots, figs, bias, ticker, interval_label):
    rows = []
    close = df_ctf["close"].to_numpy()
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

        ws = [abs(f.pivots[i+1].price - f.pivots[i].price) for i in range(len(f.pivots)-1)]
        ts_lens = [f.pivots[i+1].idx - f.pivots[i].idx for i in range(len(f.pivots)-1)]

        row = {
            "ticker": ticker,
            "interval": interval_label,
            "end_ts": df_ctf.index[f.end_idx],
            "entry_ts": df_ctf.index[entry_idx],
            "confirmation_lag": entry_idx - f.end_idx,
            "fig_type": f.type,
            "direction": f.direction,
            "confirmed": f.confirmed,
            "duration": f.duration,
            "amplitude": f.amplitude,
            "amp_pct": f.amplitude / entry_px,
            "htf_bias": bias_val,
            "with_htf": with_htf,
            "against_htf": against_htf,
            "n_pivots": len(f.pivots),
            "n_errors": sum(1 for c in f.checks if c.severity == "E" and not c.ok),
            "n_warnings": sum(1 for c in f.checks if c.severity == "W" and not c.ok),
            "entry_px": entry_px,
            "w1_w2_ratio": (ws[0]/ws[1]) if len(ws) >= 2 and ws[1] > 0 else np.nan,
            "w3_w1_ratio": (ws[2]/ws[0]) if len(ws) >= 3 and ws[0] > 0 else np.nan,
            "w4_w2_ratio": (ws[3]/ws[1]) if len(ws) >= 4 and ws[1] > 0 else np.nan,
            "avg_dur_per_wave": np.mean(ts_lens) if ts_lens else np.nan,
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
    total = len(SYMBOLS) * len(EXTRA_INTERVALS)
    done = 0
    t0 = time.time()
    skipped = []

    for ticker in SYMBOLS:
        for (yf_interval, htf_rule, period, label) in EXTRA_INTERVALS:
            done += 1
            df_raw = download_raw(ticker, yf_interval, period)
            if df_raw is None:
                skipped.append(f"{ticker}/{label}")
                continue

            df_ctf = prepare_ctf(df_raw, label)
            if df_ctf is None or len(df_ctf) < 50:
                skipped.append(f"{ticker}/{label} (too short after resample)")
                continue

            # For HTF: if label=4h, htf = daily resample of 1h raw data
            # if label=30m/15m, htf = 1h native data resample
            # if label=1w, htf = monthly resample of weekly
            htf_df_for_bias = resample_ohlc(df_ctf, htf_rule)
            if len(htf_df_for_bias) < 10:
                skipped.append(f"{ticker}/{label} (HTF too short)")
                continue

            try:
                pivots = detect_monowaves(df_ctf, atr_mult=2.5)
                classify_pivots(pivots)
                figs = match_figures(pivots)
                # htf_bias_series needs the CTF df with the htf_rule
                bias = htf_bias_series(df_ctf, htf_rule)
            except Exception as e:
                skipped.append(f"{ticker}/{label}: {e}")
                continue

            rows = figures_to_rows(df_ctf, pivots, figs, bias, ticker, label)
            all_rows.extend(rows)

            elapsed = time.time() - t0
            eta = elapsed / done * (total - done) if done > 0 else 0
            print(f"[{done:3}/{total}] {ticker:10} {label:3}  "
                  f"bars={len(df_ctf):5}  figs={len(figs):4}  rows={len(rows):4}  "
                  f"({elapsed:.0f}s eta={eta:.0f}s)")

    df_new = pd.DataFrame(all_rows)
    print(f"\nNew rows: {len(df_new)}")
    print(f"By type:\n{df_new['fig_type'].value_counts() if not df_new.empty else 'empty'}")
    print(f"By interval:\n{df_new['interval'].value_counts() if not df_new.empty else 'empty'}")

    # Merge with existing
    df_old = pd.read_parquet(OLD_PARQUET)
    print(f"Old rows: {len(df_old)}")
    df_all = pd.concat([df_old, df_new], ignore_index=True)
    print(f"Total: {len(df_all)}")
    df_all.to_parquet(OUT_PARQUET)
    print(f"Saved: {OUT_PARQUET}")
    if skipped:
        print(f"Skipped {len(skipped)}: {skipped[:5]}{'...' if len(skipped)>5 else ''}")


if __name__ == "__main__":
    main()
