"""Tests for the auto-trader entry gate (freshness + reward-first quality).

Covers the logic added across EPIC A-H that previously had no unit tests:
signal_is_fresh (time-budget freshness) and setup_quality_ok (calibration
sample, validation, sample size, expectancy floor, win-rate sanity).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # python/

import ewb.auto_trader as at  # noqa: E402


def test_signal_is_fresh_window_by_interval():
    now = at.utc_now()
    # confirmed now -> fresh on every interval
    assert at.signal_is_fresh({"interval": "1d", "entry_ts": now.isoformat()})[0] is True
    assert at.signal_is_fresh({"interval": "1h", "entry_ts": now.isoformat()})[0] is True
    # old backfill -> stale
    old = (now - pd.Timedelta(days=10)).isoformat()
    assert at.signal_is_fresh({"interval": "1d", "entry_ts": old})[0] is False
    # 1h window is ~2h; 6h ago is stale
    assert at.signal_is_fresh({"interval": "1h",
                               "entry_ts": (now - pd.Timedelta(hours=6)).isoformat()})[0] is False
    # missing / bad timestamp -> not fresh
    assert at.signal_is_fresh({"interval": "1d", "entry_ts": ""})[0] is False
    assert at.signal_is_fresh({"interval": "1d", "entry_ts": "not-a-date"})[0] is False


def test_setup_quality_ok_reward_first(monkeypatch):
    # (winrate, trades, expectancy)
    lut = {
        ("stock", "4h", "flat_htf", "long"): (0.79, 28, 0.0436),   # passes
        ("stock", "1d", "flat", "short"): (0.47, 76, 0.0014),      # EV below floor
        ("crypto", "1d", "wave3", "long"): (0.34, 200, -0.028),    # negative EV
        ("stock", "1d", "flat", "long"): (0.71, 15, 0.030),        # thin sample
        ("crypto", "1d", "flat", "long"): (0.42, 50, 0.020),       # WR below sanity
    }
    monkeypatch.setattr(at, "_SETUP_WR_CACHE", lut)

    def q(ticker, iv, pat, side, sample=100):
        return at.setup_quality_ok({"ticker": ticker, "interval": iv,
                                    "pattern": pat, "side": side, "sample_size": sample})

    assert q("NVDA", "4h", "flat_htf", "long")[0] is True            # the good one

    ok, r = q("NVDA", "1d", "flat", "short")                         # +0.14% < +0.50%
    assert not ok and "EV" in r
    ok, r = q("BTC-USD", "1d", "wave3", "long")                      # negative EV
    assert not ok and "EV" in r
    ok, r = q("NVDA", "1d", "flat", "long")                          # n=15 < 20
    assert not ok and "thin" in r
    ok, r = q("BTC-USD", "1d", "flat", "long")                       # WR 42% < 45%
    assert not ok and "WR" in r
    ok, r = q("NVDA", "1d", "triangle", "short")                     # not in LUT
    assert not ok and "unvalidated" in r
    ok, r = q("NVDA", "4h", "flat_htf", "long", sample=3)            # calib sample < 10
    assert not ok and "calib" in r


def test_asset_class_of():
    assert at.asset_class_of("BTC-USD") == "crypto"
    assert at.asset_class_of("NVDA") == "stock"
