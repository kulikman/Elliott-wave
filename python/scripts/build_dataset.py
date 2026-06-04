"""Sprint 3 — Build wide dataset.

50+ symbols × 3 timeframes → parquet of figures with features + future returns.
Used as input for Sprint 4-extended edge stats and Sprint 5 ML.
"""
from __future__ import annotations
import sys, os, warnings, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
warnings.filterwarnings("ignore")

import pandas as pd

from ewb.monowaves import detect_monowaves
from ewb.rules import classify_pivots
from ewb.figures import match_figures
from ewb.htf import htf_bias_series
from ewb.research import (
    SYMBOLS,
    download_ohlc,
    figure_rows_from_matches,
    log_processing_error,
    validate_figure_rows,
)


REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_PARQUET = os.path.join(REPO, "python", "data", "figures_wide.parquet")
os.makedirs(os.path.dirname(OUT_PARQUET), exist_ok=True)


# (interval, htf_rule, period) — limited by yfinance:
# 1d: any period | 1h: 730d max | 4h: derived via 1h resample or directly via 4h (also ≤730d) | 15m: 60d max
INTERVALS = [
    ("1d", "1W", "5y"),
    ("1h", "1D", "730d"),
]

HORIZONS = [5, 10, 20, 50, 100]

def figures_to_rows(df, figs, bias, ticker, interval):
    return figure_rows_from_matches(df, figs, bias, ticker, interval, horizons=HORIZONS)


def main():
    all_rows = []
    total = len(SYMBOLS) * len(INTERVALS)
    done = 0
    t0 = time.time()
    skipped = []
    for ticker in SYMBOLS:
        for (interval, htf_rule, period) in INTERVALS:
            done += 1
            df = download_ohlc(ticker, interval, period, include_volume=True)
            if df is None:
                skipped.append(f"{ticker}/{interval}")
                continue
            try:
                pivots = detect_monowaves(df, atr_mult=2.5)
                classify_pivots(pivots)
                figs = match_figures(pivots)
                bias = htf_bias_series(df, htf_rule)
            except Exception as e:
                log_processing_error(ticker, interval, e)
                skipped.append(f"{ticker}/{interval}:{e}")
                continue
            rows = figures_to_rows(df, figs, bias, ticker, interval)
            all_rows.extend(rows)
            elapsed = time.time() - t0
            eta = elapsed / done * (total - done)
            print(f"[{done:3}/{total}] {ticker:10} {interval:3} → {len(rows):4} rows "
                  f"(bars={len(df)}, figs={len(figs)})  elapsed={elapsed:.0f}s  eta={eta:.0f}s")

    df_out = pd.DataFrame(all_rows)
    validate_figure_rows(df_out, horizons=HORIZONS)
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
