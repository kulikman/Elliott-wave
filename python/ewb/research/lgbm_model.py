"""
Sprint 5: LightGBM probability model for flat+DC fade signals.

Predicts win probability for each setup. Used to filter low-confidence
signals and route capital more efficiently than the fixed 55% baseline.

Usage:
    python python/ewb/research/lgbm_model.py
    python python/ewb/research/lgbm_model.py --train --save-model
    python python/ewb/research/lgbm_model.py --eval-threshold 0.60
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import log_loss, roc_auc_score
from sklearn.model_selection import TimeSeriesSplit

ROOT = Path(__file__).parent.parent.parent.parent
DATA_DIR = ROOT / "python" / "data"
MODEL_OUT = ROOT / "brain-output" / "models"


FEATURES = [
    "amp_pct",
    "htf_bias",
    "with_htf",
    "against_htf",
    "confirmation_lag",
    "duration",
    "avg_dur_per_wave",
    "w1_w2_ratio",
    "w3_w1_ratio",
    "fig_type_enc",
    "direction_enc",
    "interval_enc",
]

LGBM_PARAMS = {
    "n_estimators": 300,
    "learning_rate": 0.03,
    "max_depth": 4,
    "num_leaves": 15,
    "min_child_samples": 20,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_alpha": 0.1,
    "reg_lambda": 0.1,
    "random_state": 42,
    "verbose": -1,
}


def load_and_prepare(horizon: int = 20) -> pd.DataFrame:
    df = pd.read_parquet(DATA_DIR / "figures_wide.parquet")

    # Only trade patterns
    df = df[df["fig_type"].isin(["flat", "double_corr"])].copy()

    # Target: fade win — price moves opposite to pattern direction
    dir_sign = df["direction"].map({"up": -1, "down": 1})
    df["fade_win"] = (dir_sign * df[f"signed_ret_{horizon}"]) > 0

    # Encode categoricals
    df["fig_type_enc"] = (df["fig_type"] == "double_corr").astype(int)
    df["direction_enc"] = (df["direction"] == "up").astype(int)
    df["interval_enc"] = (df["interval"] == "1h").astype(int)

    # Sort by time for time-series CV
    df = df.sort_values("entry_ts").reset_index(drop=True)

    return df


def time_series_cv(df: pd.DataFrame, n_splits: int = 5) -> dict:
    X = df[FEATURES].astype(float)
    y = df["fade_win"].astype(int)

    tscv = TimeSeriesSplit(n_splits=n_splits)
    aucs, losses, win_rates = [], [], []

    for fold, (train_idx, val_idx) in enumerate(tscv.split(X)):
        X_tr, y_tr = X.iloc[train_idx], y.iloc[train_idx]
        X_val, y_val = X.iloc[val_idx], y.iloc[val_idx]

        model = LGBMClassifier(**LGBM_PARAMS)
        model.fit(X_tr, y_tr)
        proba = model.predict_proba(X_val)[:, 1]

        auc = roc_auc_score(y_val, proba)
        ll = log_loss(y_val, proba)
        aucs.append(auc)
        losses.append(ll)
        win_rates.append(y_val.mean())
        print(f"  Fold {fold+1}: AUC={auc:.3f}  LogLoss={ll:.4f}  n={len(y_val)}  WR={y_val.mean():.3f}")

    return {"auc_mean": float(np.mean(aucs)), "auc_std": float(np.std(aucs)),
            "logloss_mean": float(np.mean(losses)), "n_folds": n_splits}


def threshold_analysis(df: pd.DataFrame, thresholds: list[float] | None = None) -> pd.DataFrame:
    """Train on first 70% of data, evaluate on last 30%, sweep probability threshold."""
    if thresholds is None:
        thresholds = [0.50, 0.52, 0.54, 0.56, 0.58, 0.60, 0.62, 0.65]

    X = df[FEATURES].astype(float)
    y = df["fade_win"].astype(int)
    ret = df["signed_ret_20"].values
    direction_sign = df["direction"].map({"up": -1, "down": 1}).values

    split = int(len(df) * 0.70)
    X_tr, y_tr = X.iloc[:split], y.iloc[:split]
    X_te = X.iloc[split:]
    y_te = y.iloc[split:]
    ret_te = ret[split:]
    dir_te = direction_sign[split:]

    model = LGBMClassifier(**LGBM_PARAMS)
    cal = CalibratedClassifierCV(model, cv=3, method="isotonic")
    cal.fit(X_tr, y_tr)
    proba = cal.predict_proba(X_te)[:, 1]

    rows = []
    for thr in thresholds:
        mask = proba >= thr
        n = mask.sum()
        if n < 10:
            continue
        win = y_te[mask].mean()
        # Simulated returns: fade = opposite direction
        fade_rets = dir_te[mask] * ret_te[mask]
        sharpe = float(fade_rets.mean() / fade_rets.std() * np.sqrt(252)) if fade_rets.std() > 0 else 0
        rows.append({"threshold": thr, "n_trades": int(n), "win_rate": round(float(win), 3),
                     "mean_ret": round(float(fade_rets.mean()), 4), "sharpe_ann": round(sharpe, 2)})

    return pd.DataFrame(rows)


def feature_importance(df: pd.DataFrame) -> pd.DataFrame:
    X = df[FEATURES].astype(float)
    y = df["fade_win"].astype(int)
    model = LGBMClassifier(**LGBM_PARAMS)
    model.fit(X, y)
    imp = pd.DataFrame({"feature": FEATURES, "importance": model.feature_importances_})
    return imp.sort_values("importance", ascending=False)


def train_full_model(df: pd.DataFrame) -> CalibratedClassifierCV:
    X = df[FEATURES].astype(float)
    y = df["fade_win"].astype(int)
    model = LGBMClassifier(**LGBM_PARAMS)
    cal = CalibratedClassifierCV(model, cv=5, method="isotonic")
    cal.fit(X, y)
    return cal


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--horizon", type=int, default=20)
    parser.add_argument("--train", action="store_true", help="Train and evaluate")
    parser.add_argument("--save-model", action="store_true")
    parser.add_argument("--eval-threshold", type=float, default=None)
    args = parser.parse_args()

    print("=== Sprint 5: LightGBM Probability Model ===")
    print(f"Horizon: {args.horizon} bars | Features: {len(FEATURES)}")

    df = load_and_prepare(horizon=args.horizon)
    print(f"Dataset: {len(df)} trades | flat={int((df.fig_type=='flat').sum())} DC={int((df.fig_type=='double_corr').sum())}")
    print(f"Baseline win rate: {df['fade_win'].mean():.3f}")

    print("\n--- Time-series CV (5 folds) ---")
    cv_stats = time_series_cv(df, n_splits=5)
    print(f"CV AUC: {cv_stats['auc_mean']:.3f} ± {cv_stats['auc_std']:.3f}")
    print(f"CV LogLoss: {cv_stats['logloss_mean']:.4f}")

    print("\n--- Feature Importance ---")
    imp = feature_importance(df)
    print(imp.to_string(index=False))

    print("\n--- Threshold Analysis (train 70% / eval 30%) ---")
    thr_df = threshold_analysis(df)
    print(thr_df.to_string(index=False))

    if args.eval_threshold:
        row = thr_df[thr_df["threshold"] == args.eval_threshold]
        if not row.empty:
            r = row.iloc[0]
            print(f"\nAt threshold={args.eval_threshold}: n={r.n_trades} WR={r.win_rate} Sharpe={r.sharpe_ann}")

    if args.save_model:
        import pickle
        MODEL_OUT.mkdir(parents=True, exist_ok=True)
        print("\n--- Training full model ---")
        cal = train_full_model(df)
        model_path = MODEL_OUT / f"lgbm_fade_h{args.horizon}.pkl"
        with open(model_path, "wb") as f:
            pickle.dump({"model": cal, "features": FEATURES, "horizon": args.horizon,
                         "cv_stats": cv_stats}, f)
        print(f"Saved: {model_path}")

        # Save threshold table
        thr_path = MODEL_OUT / f"lgbm_thresholds_h{args.horizon}.json"
        thr_path.write_text(json.dumps(thr_df.to_dict(orient="records"), indent=2))
        print(f"Saved: {thr_path}")


if __name__ == "__main__":
    main()
