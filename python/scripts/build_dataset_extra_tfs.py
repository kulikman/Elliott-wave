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

import pandas as pd

from ewb.monowaves import detect_monowaves
from ewb.rules import classify_pivots
from ewb.figures import match_figures
from ewb.htf import htf_bias_series, resample_ohlc
from ewb.research import (
    SYMBOLS,
    download_ohlc,
    figure_rows_from_matches,
    log_processing_error,
    validate_figure_rows,
)


REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OLD_PARQUET = os.path.join(REPO, "python", "data", "figures_wide.parquet")
OUT_PARQUET = os.path.join(REPO, "python", "data", "figures_all_tfs.parquet")

HORIZONS = [5, 10, 20, 50, 100]

# (yf_interval, pandas_htf_rule, yf_period, label)
EXTRA_INTERVALS = [
    ("1wk",  "1ME",  "10y",  "1w"),
    ("1h",   "1D",   "730d", "4h"),   # resample 1h→4h
    ("30m",  "1h",   "60d",  "30m"),
    ("15m",  "1h",   "60d",  "15m"),
]

def prepare_ctf(df_raw, label):
    """Resample if needed (1h→4h), return ctf DataFrame."""
    if label == "4h":
        return resample_ohlc(df_raw, "4h")
    return df_raw


def figures_to_rows(df_ctf, figs, bias, ticker, interval_label):
    return figure_rows_from_matches(
        df_ctf,
        figs,
        bias,
        ticker,
        interval_label,
        horizons=HORIZONS,
        include_w5_ratio=False,
    )


def main():
    all_rows = []
    total = len(SYMBOLS) * len(EXTRA_INTERVALS)
    done = 0
    t0 = time.time()
    skipped = []

    for ticker in SYMBOLS:
        for (yf_interval, htf_rule, period, label) in EXTRA_INTERVALS:
            done += 1
            df_raw = download_ohlc(ticker, yf_interval, period)
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
                log_processing_error(ticker, label, e)
                skipped.append(f"{ticker}/{label}: {e}")
                continue

            rows = figures_to_rows(df_ctf, figs, bias, ticker, label)
            all_rows.extend(rows)

            elapsed = time.time() - t0
            eta = elapsed / done * (total - done) if done > 0 else 0
            print(f"[{done:3}/{total}] {ticker:10} {label:3}  "
                  f"bars={len(df_ctf):5}  figs={len(figs):4}  rows={len(rows):4}  "
                  f"({elapsed:.0f}s eta={eta:.0f}s)")

    df_new = pd.DataFrame(all_rows)
    validate_figure_rows(df_new, horizons=HORIZONS)
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
