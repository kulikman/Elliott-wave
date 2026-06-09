"""
Sprint 7: Production FastAPI prediction service for EWB LightGBM probability signals.

Endpoints:
  GET  /health                  — liveness probe
  GET  /api/v1/model/info       — model metadata
  POST /api/v1/predict          — single figure → lgbm_prob + full trade signal
  POST /api/v1/predict/batch    — list of figures → list of signals
  GET  /api/v1/signals          — latest signals from brain-output/signals/

Run:
    uvicorn python.ewb.prediction_api:app --reload --port 8001
    # or from project root:
    python -m uvicorn ewb.prediction_api:app --port 8001
"""
from __future__ import annotations

import json
import math
import pickle
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

import importlib.util as _ilu
import types as _types

# Import only from probability.py — bypass research/__init__.py (which pulls yfinance)
_spec = _ilu.spec_from_file_location(
    "ewb.research.probability",
    Path(__file__).parent / "research" / "probability.py",
)
_prob_mod: _types.ModuleType = _ilu.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_prob_mod)  # type: ignore[union-attr]

build_probability_signal = _prob_mod.build_probability_signal
lgbm_probability = _prob_mod.lgbm_probability
load_probability_calibration = _prob_mod.load_probability_calibration

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO = Path(__file__).resolve().parents[2]
SIGNALS_DIR = REPO / "brain-output" / "signals"
MODEL_DIR = REPO / "brain-output" / "models"
CALIBRATION_FILE = SIGNALS_DIR / "probability_signals_1h_buy-sell.json"
_MODEL_PATH = MODEL_DIR / "lgbm_fade_h20.pkl"

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="EWB Prediction API",
    version="1.0.0",
    description="LightGBM probability predictions for Elliott Wave setups (Sprint 7)",
)

# ---------------------------------------------------------------------------
# Lazy-loaded calibration
# ---------------------------------------------------------------------------
_CALIBRATION: dict | None = None


def _get_calibration() -> dict | None:
    global _CALIBRATION
    if _CALIBRATION is not None:
        return _CALIBRATION
    if not CALIBRATION_FILE.exists():
        return None
    try:
        _CALIBRATION = load_probability_calibration(str(CALIBRATION_FILE))
    except Exception:
        return None
    return _CALIBRATION


def _get_model_meta() -> dict | None:
    if not _MODEL_PATH.exists():
        return None
    try:
        with open(_MODEL_PATH, "rb") as f:
            bundle = pickle.load(f)
        return {
            "path": str(_MODEL_PATH),
            "features": bundle.get("features", []),
            "horizon": bundle.get("horizon", 20),
            "cv_stats": bundle.get("cv_stats", {}),
        }
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class FigureInput(BaseModel):
    """Single Elliott Wave figure — features needed for LightGBM prediction."""

    fig_type: str = Field(..., description="'flat' or 'double_corr'")
    direction: str = Field(..., description="'up' or 'down'")
    interval: str = Field(default="1h", description="'1h' or '4h' etc.")
    amp_pct: float = Field(..., description="Figure amplitude as % of price")
    htf_bias: int = Field(default=0, description="-1/0/1 HTF bias")
    with_htf: bool = Field(default=False, description="Aligned with HTF bias")
    against_htf: bool = Field(default=False, description="Against HTF bias")
    confirmation_lag: int = Field(default=0, description="Bars from figure end to entry")
    duration: int = Field(default=5, description="Total bars in figure")
    avg_dur_per_wave: float = Field(default=1.0, description="Mean bars per wave")
    w1_w2_ratio: float = Field(default=0.5, description="W2/W1 length ratio")
    w3_w1_ratio: float = Field(default=1.0, description="W3/W1 length ratio")
    entry_px: float | None = Field(default=None, description="Entry price for levels calc")
    amplitude: float | None = Field(default=None, description="Absolute amplitude for stop/target")
    lgbm_threshold: float = Field(default=0.54, description="Probability threshold for action")

    @field_validator("fig_type")
    @classmethod
    def validate_fig_type(cls, v: str) -> str:
        if v not in {"flat", "double_corr", "impulse", "zigzag", "triangle", "terminal"}:
            raise ValueError(f"Unknown fig_type: {v}")
        return v

    @field_validator("direction")
    @classmethod
    def validate_direction(cls, v: str) -> str:
        if v not in {"up", "down"}:
            raise ValueError("direction must be 'up' or 'down'")
        return v


class BatchInput(BaseModel):
    figures: list[FigureInput]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/health")
def health() -> dict:
    model_ok = _MODEL_PATH.exists()
    cal_ok = CALIBRATION_FILE.exists()
    return {
        "status": "ok" if model_ok else "degraded",
        "model_loaded": model_ok,
        "calibration_loaded": cal_ok,
    }


@app.get("/api/v1/model/info")
def model_info() -> JSONResponse:
    meta = _get_model_meta()
    if meta is None:
        raise HTTPException(status_code=503, detail="Model not found — run lgbm_model.py --save-model")
    return JSONResponse(content=meta)


@app.post("/api/v1/predict")
def predict(figure: FigureInput) -> JSONResponse:
    """
    Run LightGBM + calibrated probability for a single figure.
    Returns full trade signal (action, risk_box, lgbm_prob, etc.).
    """
    lgbm_prob = lgbm_probability(
        fig_type=figure.fig_type,
        direction=figure.direction,
        interval=figure.interval,
        amp_pct=figure.amp_pct,
        htf_bias=figure.htf_bias,
        with_htf=figure.with_htf,
        against_htf=figure.against_htf,
        confirmation_lag=figure.confirmation_lag,
        duration=figure.duration,
        avg_dur_per_wave=figure.avg_dur_per_wave,
        w1_w2_ratio=figure.w1_w2_ratio,
        w3_w1_ratio=figure.w3_w1_ratio,
    )

    calibration = _get_calibration() or {"rows": [], "model_version": "none", "lookup_priority": []}

    signal = build_probability_signal(
        calibration=calibration,
        fig_type=figure.fig_type,
        interval=figure.interval,
        direction=figure.direction,
        entry_px=figure.entry_px,
        amplitude=figure.amplitude,
        lgbm_prob=lgbm_prob,
        lgbm_threshold=figure.lgbm_threshold,
    )

    return JSONResponse(content=_clean_signal(signal))


@app.post("/api/v1/predict/batch")
def predict_batch(batch: BatchInput) -> JSONResponse:
    """Predict for a list of figures. Returns list of signals in same order."""
    calibration = _get_calibration() or {"rows": [], "model_version": "none", "lookup_priority": []}
    results: list[dict] = []

    for figure in batch.figures:
        lgbm_prob = lgbm_probability(
            fig_type=figure.fig_type,
            direction=figure.direction,
            interval=figure.interval,
            amp_pct=figure.amp_pct,
            htf_bias=figure.htf_bias,
            with_htf=figure.with_htf,
            against_htf=figure.against_htf,
            confirmation_lag=figure.confirmation_lag,
            duration=figure.duration,
            avg_dur_per_wave=figure.avg_dur_per_wave,
            w1_w2_ratio=figure.w1_w2_ratio,
            w3_w1_ratio=figure.w3_w1_ratio,
        )
        signal = build_probability_signal(
            calibration=calibration,
            fig_type=figure.fig_type,
            interval=figure.interval,
            direction=figure.direction,
            entry_px=figure.entry_px,
            amplitude=figure.amplitude,
            lgbm_prob=lgbm_prob,
            lgbm_threshold=figure.lgbm_threshold,
        )
        results.append(_clean_signal(signal))

    return JSONResponse(content={"count": len(results), "signals": results})


@app.get("/api/v1/signals")
def latest_signals(
    limit: int = 20,
    action: str | None = None,
    interval: str | None = None,
) -> JSONResponse:
    """
    Return latest pre-computed signals from brain-output/signals/.
    Optional filters: action ('buy'/'sell'/'wait'), interval ('1h'/'4h').
    """
    signal_files = [
        SIGNALS_DIR / "probability_signals_1h_buy-sell_fresh-48h.json",
        SIGNALS_DIR / "probability_signals_1h_buy-sell.json",
        SIGNALS_DIR / "daily_report.json",
    ]

    # Try fresh-48h first, fall back to full set
    signals: list[dict] = []
    source_file = None
    for f in signal_files:
        if not f.exists():
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            raw = data.get("signals", [])
            if raw:
                signals = raw
                source_file = f.name
                break
        except Exception:
            continue

    if not signals:
        return JSONResponse(content={"count": 0, "signals": [], "source": None})

    # Apply filters
    if action:
        signals = [s for s in signals if s.get("recommended_action") == action]
    if interval:
        signals = [s for s in signals if s.get("interval") == interval]

    signals = signals[:limit]
    return JSONResponse(content={
        "count": len(signals),
        "signals": signals,
        "source": source_file,
        "limit": limit,
    })


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _clean_signal(signal: dict) -> dict[str, Any]:
    """Recursively replace NaN/Inf with None for JSON serialisability."""
    out: dict[str, Any] = {}
    for k, v in signal.items():
        if isinstance(v, dict):
            out[k] = _clean_signal(v)
        elif isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            out[k] = None
        else:
            out[k] = v
    return out


# ---------------------------------------------------------------------------
# Dev entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("ewb.prediction_api:app", host="0.0.0.0", port=8001, reload=True)
