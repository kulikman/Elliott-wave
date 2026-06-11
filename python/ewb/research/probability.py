"""Probability calibration helpers for indicator signal contracts."""
from __future__ import annotations

import copy
import json
import math
import pickle
from pathlib import Path
from typing import Iterable

import pandas as pd

# LightGBM model path (Sprint 5)
_LGBM_MODEL_PATH = Path(__file__).parent.parent.parent.parent / "brain-output" / "models" / "lgbm_fade_h20.pkl"
_LGBM_BUNDLE: dict | None = None
_LGBM_FEATURES = [
    "amp_pct", "htf_bias", "with_htf", "against_htf",
    "confirmation_lag", "duration", "avg_dur_per_wave",
    "w1_w2_ratio", "w3_w1_ratio", "fig_type_enc", "direction_enc", "interval_enc",
]


def _load_lgbm() -> dict | None:
    global _LGBM_BUNDLE
    if _LGBM_BUNDLE is not None:
        return _LGBM_BUNDLE
    if not _LGBM_MODEL_PATH.exists():
        return None
    try:
        with open(_LGBM_MODEL_PATH, "rb") as f:
            _LGBM_BUNDLE = pickle.load(f)
    except Exception:
        return None
    return _LGBM_BUNDLE


def lgbm_probability(
    fig_type: str,
    direction: str,
    interval: str,
    amp_pct: float,
    htf_bias: int,
    with_htf: bool,
    against_htf: bool,
    confirmation_lag: int,
    duration: int,
    avg_dur_per_wave: float,
    w1_w2_ratio: float,
    w3_w1_ratio: float,
) -> float | None:
    """Return LightGBM P(fade_win) for a flat/DC figure. None if model unavailable."""
    bundle = _load_lgbm()
    if bundle is None:
        return None
    model = bundle["model"]
    row = {
        "amp_pct": amp_pct,
        "htf_bias": htf_bias,
        "with_htf": int(with_htf),
        "against_htf": int(against_htf),
        "confirmation_lag": confirmation_lag,
        "duration": duration,
        "avg_dur_per_wave": avg_dur_per_wave,
        "w1_w2_ratio": w1_w2_ratio,
        "w3_w1_ratio": w3_w1_ratio,
        "fig_type_enc": int(fig_type == "double_corr"),
        "direction_enc": int(direction == "up"),
        "interval_enc": int(interval == "1h"),
    }
    X = pd.DataFrame([row])[_LGBM_FEATURES].astype(float)
    try:
        prob = float(model.predict_proba(X)[0, 1])
    except Exception:
        return None
    return prob


TRADE_PATTERNS = {"flat", "double_corr"}
SKIP_PATTERNS = {"impulse", "triangle"}
LOOKUP_PRIORITY = [
    "fig_type+interval+side",
    "fig_type+interval",
    "fig_type+side",
    "fig_type",
]


def confidence_for_n(n: int) -> str:
    """Map sample size to a conservative confidence label."""
    if n < 50:
        return "low"
    if n < 150:
        return "medium"
    if n < 400:
        return "high"
    return "very_high"


def recommended_action(fig_type: str, side: str | None) -> str:
    """Return the user-facing trading action for a calibrated setup."""
    if fig_type in SKIP_PATTERNS:
        return "skip"
    if fig_type not in TRADE_PATTERNS:
        return "wait"
    if side == "long":
        return "buy"
    if side == "short":
        return "sell"
    return "wait"


def side_probabilities(side: str | None, p_trade_win: float) -> tuple[float | None, float | None]:
    """Convert side-specific win probability into p_up/p_down."""
    if side == "long":
        return p_trade_win, 1.0 - p_trade_win
    if side == "short":
        return 1.0 - p_trade_win, p_trade_win
    return None, None


def fade_side(direction: str) -> str | None:
    """Return the fade side for a finished figure direction."""
    if direction == "up":
        return "short"
    if direction == "down":
        return "long"
    return None


def price_levels(side: str | None, entry_px: float | None, amplitude: float | None) -> dict:
    """Calculate stop/target prices from entry and absolute figure amplitude."""
    if side not in {"long", "short"} or entry_px is None or amplitude is None:
        return {"entry_px": entry_px, "stop_px": None, "target_px": None}
    if entry_px <= 0 or amplitude <= 0:
        return {"entry_px": entry_px, "stop_px": None, "target_px": None}
    if side == "long":
        return {
            "entry_px": entry_px,
            "stop_px": entry_px - amplitude,
            "target_px": entry_px + amplitude,
        }
    return {
        "entry_px": entry_px,
        "stop_px": entry_px + amplitude,
        "target_px": entry_px - amplitude,
    }


def load_probability_calibration(path: str) -> dict:
    """Load a probability calibration JSON payload."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def lookup_probability_row(
    calibration: dict,
    fig_type: str,
    interval: str,
    side: str | None,
) -> dict | None:
    """Find the best matching calibration row by configured priority."""
    rows = calibration.get("rows", [])
    by_level_key = {(row.get("level"), row.get("key")): row for row in rows}
    candidates = {
        "fig_type+interval+side": (
            f"{fig_type}|{interval}|{side}" if side is not None else None
        ),
        "fig_type+interval": f"{fig_type}|{interval}",
        "fig_type+side": f"{fig_type}|{side}" if side is not None else None,
        "fig_type": fig_type,
    }
    for level in calibration.get("lookup_priority", LOOKUP_PRIORITY):
        key = candidates.get(level)
        if key is None:
            continue
        row = by_level_key.get((level, key))
        if row is not None:
            return row
    return None


def build_probability_signal(
    calibration: dict,
    fig_type: str,
    interval: str,
    direction: str,
    entry_px: float | None = None,
    amplitude: float | None = None,
    lgbm_prob: float | None = None,
    lgbm_threshold: float = 0.54,
) -> dict:
    """Build the runtime v0 signal contract for one detected figure."""
    side = fade_side(direction)
    row = lookup_probability_row(calibration, fig_type, interval, side)
    action = recommended_action(fig_type, side)
    is_trade_pattern = fig_type in TRADE_PATTERNS
    levels = (
        price_levels(side, entry_px, amplitude)
        if is_trade_pattern
        else {"entry_px": entry_px, "stop_px": None, "target_px": None}
    )

    if row is None:
        p_trade_win = None
        p_up = p_down = None
        expected = None
        confidence = "unknown"
        sample_size = 0
        lookup_key = None
        lookup_level = None
    else:
        p_trade_win = row.get("p_trade_win")
        p_up = row.get("p_up")
        p_down = row.get("p_down")
        expected = row.get("expected_net_return")
        confidence = row.get("confidence", "unknown")
        sample_size = row.get("n", 0)
        lookup_key = row.get("key")
        lookup_level = row.get("level")
        action = row.get("recommended_action", action)

    if fig_type in SKIP_PATTERNS:
        action = "skip"

    # LightGBM v1 filter: if model available and p < threshold → downgrade to wait
    lgbm_action_override = None
    if lgbm_prob is not None and is_trade_pattern:
        if lgbm_prob < lgbm_threshold:
            lgbm_action_override = "wait"  # model says low confidence

    effective_action = lgbm_action_override if lgbm_action_override else action

    signal = {
        "pattern": fig_type,
        "interval": interval,
        "direction": direction,
        "side": side,
        "recommended_action": effective_action,
        "p_up": p_up,
        "p_down": p_down,
        "p_trade_win": p_trade_win,
        "expected_net_return": expected,
        "confidence": confidence,
        "sample_size": sample_size,
        "entry_zone": (
            "fade_after_confirmed_pattern"
            if is_trade_pattern and effective_action != "wait"
            else "none"
        ),
        "stop": "figure_amplitude" if is_trade_pattern and effective_action != "wait" else "none",
        "target": "full_retrace" if is_trade_pattern and effective_action != "wait" else "none",
        "risk_box": {
            **levels,
            "amplitude": amplitude,
        },
        "lookup_level": lookup_level,
        "lookup_key": lookup_key,
        "source_model_version": calibration.get("model_version", "unknown"),
        "lgbm_prob": lgbm_prob,
        "lgbm_threshold": lgbm_threshold if lgbm_prob is not None else None,
        "lgbm_action": lgbm_action_override,
    }
    return copy.deepcopy(signal)


def probability_signal_from_figure(
    calibration: dict,
    figure,
    df: pd.DataFrame,
    ticker: str,
    interval: str,
) -> dict | None:
    """Build a probability signal from a matched Figure and its OHLC frame."""
    if not getattr(figure, "pivots", None):
        return None
    entry_idx = figure.pivots[-1].confirmation_idx
    if entry_idx < 0:
        entry_idx = figure.end_idx
    if entry_idx < 0 or entry_idx >= len(df):
        return None

    entry_px = float(df["close"].iloc[entry_idx])
    signal = build_probability_signal(
        calibration,
        fig_type=figure.type,
        interval=interval,
        direction=figure.direction,
        entry_px=entry_px,
        amplitude=float(figure.amplitude),
    )
    # AKU-0036/0038/0060 — time budget of confirmation. The post-pattern move
    # must confirm (break the pattern's trendline) within the duration of the
    # final wave (C of a flat, Y of a double correction). confirmation_lag is
    # bars from the pattern's last pivot to the confirmation bar; last_wave_bars
    # is the duration of that final wave. A confirmation slower than the final
    # wave means the structure is suspect (not a clean fade).
    confirmation_lag = int(entry_idx - figure.end_idx)
    last_wave_bars = None
    if len(figure.pivots) >= 2:
        last_wave_bars = int(figure.pivots[-1].idx - figure.pivots[-2].idx)
    time_budget_ok = (
        last_wave_bars is None
        or last_wave_bars <= 0
        or confirmation_lag <= last_wave_bars
    )
    signal.update({
        "ticker": ticker,
        "entry_idx": int(entry_idx),
        "entry_ts": str(df.index[entry_idx]),
        "end_idx": int(figure.end_idx),
        "end_ts": str(df.index[figure.end_idx]) if figure.end_idx < len(df) else None,
        "confirmation_lag": confirmation_lag,
        "last_wave_bars": last_wave_bars,
        "time_budget_ok": bool(time_budget_ok),
        "confirmed": bool(getattr(figure, "confirmed", False)),
        "n_checks": len(getattr(figure, "checks", [])),
        "n_errors": sum(
            1
            for check in getattr(figure, "checks", [])
            if getattr(check, "severity", "") == "E" and not getattr(check, "ok", False)
        ),
    })
    return signal


def _clean_float(value) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(out) or math.isinf(out):
        return None
    return out


def _group_key(row: dict, group_cols: Iterable[str]) -> str:
    return "|".join(str(row[col]) for col in group_cols)


def calibration_rows(
    trades: pd.DataFrame,
    group_cols: list[str],
    min_n: int = 1,
) -> list[dict]:
    """Build probability rows for a grouping over trade records."""
    required = {"fig_type", "net_ret", "win", "exit_reason"}
    missing = sorted(required - set(trades.columns))
    if missing:
        raise ValueError(f"trades missing required columns: {', '.join(missing)}")

    rows: list[dict] = []
    for keys, grp in trades.groupby(group_cols, dropna=False):
        if len(grp) < min_n:
            continue
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = {col: key for col, key in zip(group_cols, keys)}
        fig_type = str(row.get("fig_type", ""))
        side = row.get("side")
        side = str(side) if side is not None and not pd.isna(side) else None
        p_trade_win = float(grp["win"].mean())
        p_up, p_down = side_probabilities(side, p_trade_win)
        returns = grp["net_ret"]
        wins = returns[grp["win"]]
        losses = returns[~grp["win"]]
        n = int(len(grp))
        avg_win = _clean_float(wins.mean()) if len(wins) else 0.0
        avg_loss = _clean_float(losses.mean()) if len(losses) else 0.0
        payoff = (
            abs(avg_win / avg_loss)
            if avg_win is not None and avg_loss not in (None, 0.0)
            else None
        )

        rows.append({
            "key": _group_key(row, group_cols),
            "level": "+".join(group_cols),
            **row,
            "n": n,
            "p_trade_win": p_trade_win,
            "p_up": p_up,
            "p_down": p_down,
            "expected_net_return": float(returns.mean()),
            "median_net_return": float(returns.median()),
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "payoff_ratio": payoff,
            "p_tp": float((grp["exit_reason"] == "tp").mean()),
            "p_sl": float((grp["exit_reason"] == "sl").mean()),
            "p_time": float((grp["exit_reason"] == "time").mean()),
            "confidence": confidence_for_n(n),
            "recommended_action": recommended_action(fig_type, side),
            "entry_zone": (
                "fade_after_confirmed_pattern"
                if fig_type in TRADE_PATTERNS
                else "none"
            ),
            "stop": "figure_amplitude" if fig_type in TRADE_PATTERNS else "none",
            "target": "full_retrace" if fig_type in TRADE_PATTERNS else "none",
        })
    return rows


def build_probability_calibration(trades: pd.DataFrame, min_n: int = 1) -> dict:
    """Build the v0 machine-readable calibration payload."""
    levels = [
        ["fig_type", "interval", "side"],
        ["fig_type", "interval"],
        ["fig_type", "side"],
        ["fig_type"],
    ]
    rows: list[dict] = []
    for group_cols in levels:
        rows.extend(calibration_rows(trades, group_cols, min_n=min_n))
    return {
        "model_version": "probability-calibration-v0",
        "source": "python/data/trades_sprint6.parquet",
        "trade_patterns": sorted(TRADE_PATTERNS),
        "skip_patterns": sorted(SKIP_PATTERNS),
        "lookup_priority": [
            *LOOKUP_PRIORITY,
        ],
        "rows": rows,
    }
