"""
Sprint 5: LightGBM-filtered backtest vs baseline.

Compares:
  - Baseline: all flat+DC fade trades (Sharpe 2.82 full dataset)
  - Filtered: only trades where LightGBM P(win) >= threshold

Usage:
    python python/ewb/research/lgbm_backtest.py
    python python/ewb/research/lgbm_backtest.py --threshold 0.54
"""
from __future__ import annotations

import argparse
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent.parent.parent.parent
DATA_DIR = ROOT / "python" / "data"
MODEL_DIR = ROOT / "brain-output" / "models"

FEATURES = [
    "amp_pct", "htf_bias", "with_htf", "against_htf",
    "confirmation_lag", "duration", "avg_dur_per_wave",
    "w1_w2_ratio", "w3_w1_ratio", "fig_type_enc", "direction_enc", "interval_enc",
]


def sharpe(rets: pd.Series, ann: int = 252) -> float:
    if len(rets) < 5 or rets.std() == 0:
        return 0.0
    return float(rets.mean() / rets.std() * np.sqrt(ann))


def load_figures(horizon: int = 20) -> pd.DataFrame:
    df = pd.read_parquet(DATA_DIR / "figures_wide.parquet")
    df = df[df["fig_type"].isin(["flat", "double_corr"])].copy()
    dir_sign = df["direction"].map({"up": -1, "down": 1})
    df["fade_win"] = (dir_sign * df[f"signed_ret_{horizon}"]) > 0
    df["fade_ret"] = dir_sign * df[f"signed_ret_{horizon}"]
    df["fig_type_enc"] = (df["fig_type"] == "double_corr").astype(int)
    df["direction_enc"] = (df["direction"] == "up").astype(int)
    df["interval_enc"] = (df["interval"] == "1h").astype(int)
    df = df.sort_values("entry_ts").reset_index(drop=True)
    return df


def run_comparison(threshold: float = 0.54, horizon: int = 20) -> None:
    # Load model and data
    model_path = MODEL_DIR / f"lgbm_fade_h{horizon}.pkl"
    if not model_path.exists():
        print(f"Model not found: {model_path}")
        print("Run: python python/ewb/research/lgbm_model.py --train --save-model")
        return

    with open(model_path, "rb") as f:
        bundle = pickle.load(f)
    model = bundle["model"]

    df = load_figures(horizon)
    X = df[FEATURES].astype(float)
    df["lgbm_prob"] = model.predict_proba(X)[:, 1]

    # Time-based train/test split (last 30% = test)
    split = int(len(df) * 0.70)
    test = df.iloc[split:].copy()

    print(f"\n=== LightGBM-filtered Backtest (horizon={horizon} bars) ===")
    print(f"Test set: {len(test)} trades ({test['entry_ts'].min().date()} → {test['entry_ts'].max().date()})")

    # --- Baseline ---
    base_rets = test["fade_ret"]
    print(f"\nBaseline (all trades, n={len(test)}):")
    print(f"  WR={test['fade_win'].mean():.3f}  mean_ret={base_rets.mean():.4f}  "
          f"Sharpe(ann)={sharpe(base_rets):.2f}")

    # --- Filtered ---
    filtered = test[test["lgbm_prob"] >= threshold]
    if len(filtered) < 10:
        print(f"Too few trades at threshold={threshold}")
        return
    filt_rets = filtered["fade_ret"]
    print(f"\nFiltered (P>={threshold}, n={len(filtered)}, {len(filtered)/len(test):.0%} retained):")
    print(f"  WR={filtered['fade_win'].mean():.3f}  mean_ret={filt_rets.mean():.4f}  "
          f"Sharpe(ann)={sharpe(filt_rets):.2f}")

    # --- Breakdown by pattern ---
    print("\nBreakdown by pattern (filtered):")
    for pt in ["flat", "double_corr"]:
        sub = filtered[filtered["fig_type"] == pt]
        if len(sub) < 5:
            continue
        sr = sharpe(sub["fade_ret"])
        print(f"  {pt:12s}: n={len(sub):3d}  WR={sub['fade_win'].mean():.3f}  Sharpe={sr:.2f}")

    # --- Probability calibration check ---
    buckets = pd.cut(test["lgbm_prob"], bins=[0, 0.45, 0.50, 0.55, 0.60, 0.65, 1.0])
    calib = test.groupby(buckets, observed=True)["fade_win"].agg(["mean", "count"])
    calib.columns = ["actual_wr", "n"]
    print("\nCalibration (predicted prob → actual WR):")
    print(calib.to_string())

    # --- Threshold sweep ---
    print("\nThreshold sweep (test set):")
    print(f"{'thr':>5}  {'n':>5}  {'wr':>6}  {'mean_ret':>9}  {'sharpe':>7}")
    for thr in [0.50, 0.52, 0.54, 0.56, 0.58, 0.60, 0.62, 0.65]:
        sub = test[test["lgbm_prob"] >= thr]
        if len(sub) < 10:
            break
        sr = sharpe(sub["fade_ret"])
        print(f"{thr:5.2f}  {len(sub):5d}  {sub['fade_win'].mean():6.3f}  "
              f"{sub['fade_ret'].mean():9.4f}  {sr:7.2f}")

    # --- Feature insight for rejected trades ---
    rejected = test[test["lgbm_prob"] < threshold]
    if len(rejected) > 10:
        print(f"\nRejected trades (n={len(rejected)}) — top signals of why model rejected:")
        for feat in ["w3_w1_ratio", "w1_w2_ratio", "amp_pct"]:
            acc = filtered[feat].mean()
            rej = rejected[feat].mean()
            print(f"  {feat:20s}: accepted={acc:.3f}  rejected={rej:.3f}  diff={acc-rej:+.3f}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=float, default=0.54)
    parser.add_argument("--horizon", type=int, default=20)
    args = parser.parse_args()
    run_comparison(threshold=args.threshold, horizon=args.horizon)


if __name__ == "__main__":
    main()
