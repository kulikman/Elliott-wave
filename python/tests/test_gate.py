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
from ewb.strategy_system import asset_class_of  # noqa: E402


def test_signal_is_fresh_window_by_interval():
    # Crypto = wall-clock (24/7). Use a crypto ticker for deterministic checks.
    now = at.utc_now()
    C = lambda iv, ts: at.signal_is_fresh({"ticker": "BTC-USD", "interval": iv, "entry_ts": ts})
    # confirmed now -> fresh on every interval
    assert C("1d", now.isoformat())[0] is True
    assert C("1h", now.isoformat())[0] is True
    # old backfill -> stale
    assert C("1d", (now - pd.Timedelta(days=10)).isoformat())[0] is False
    # 1h window is ~2h; 6h ago is stale
    assert C("1h", (now - pd.Timedelta(hours=6)).isoformat())[0] is False
    # missing / bad timestamp -> not fresh
    assert C("1d", "")[0] is False
    assert C("1d", "not-a-date")[0] is False


def test_signal_is_fresh_stock_trading_time(monkeypatch):
    """Stocks age in NYSE trading time: a Friday-close signal is still fresh at
    Monday's open (weekend gap adds ~0 trading time), but a genuinely old signal
    is stale."""
    mon = pd.Timestamp("2026-06-15 14:00", tz="UTC")   # Monday 10:00 ET (just after open)
    monkeypatch.setattr(at, "utc_now", lambda: mon)
    S = lambda iv, ts: at.signal_is_fresh({"ticker": "GE", "interval": iv, "entry_ts": ts})
    fri_close = pd.Timestamp("2026-06-12 20:00", tz="UTC")   # Fri 16:00 ET
    # Friday daily signal, checked Monday morning -> ~0 trading time elapsed -> fresh
    assert S("1d", fri_close.isoformat())[0] is True
    # A 10-calendar-day-old stock signal is still stale (≈7 sessions of trading time)
    assert S("1d", (mon - pd.Timedelta(days=10)).isoformat())[0] is False


def test_setup_quality_ok_reward_first(monkeypatch):
    # (winrate, trades, expectancy)
    lut = {
        ("stock", "4h", "flat_htf", "long"): (0.79, 35, 0.0436),   # passes (flat_htf min_n=30)
        ("stock", "1d", "flat", "short"): (0.47, 76, 0.0014),      # EV below floor
        ("crypto", "1d", "wave3", "long"): (0.34, 200, -0.028),    # negative EV
        ("stock", "1d", "flat", "long"): (0.71, 15, 0.030),        # thin sample (flat min_n=20)
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


def test_setup_quality_ok_ltf_only(monkeypatch):
    """EWB_LTF_ONLY blocks 1d/1w entries (trade only 1h/4h) while keeping the
    LTF setups; default off keeps 1d/1w."""
    lut = {
        ("stock", "4h", "flat_htf", "long"): (0.76, 42, 0.0405),   # LTF — keep (flat_htf min_n=30)
        ("stock", "1d", "wave3", "long"): (0.50, 55, 0.0402),      # HTF — strong, but off under LTF-only (wave3 min_n=50)
    }
    monkeypatch.setattr(at, "_SETUP_WR_CACHE", lut)

    def q(ticker, iv, pat, side):
        return at.setup_quality_ok({"ticker": ticker, "interval": iv,
                                    "pattern": pat, "side": side, "sample_size": 100})

    # LTF-only ON: 1d blocked, 4h still allowed
    monkeypatch.setattr(at, "LTF_ONLY", True)
    ok, r = q("NVDA", "1d", "wave3", "long")
    assert not ok and "LTF-only" in r
    assert q("NVDA", "4h", "flat_htf", "long")[0] is True

    # default OFF: the 1d setup passes (its own validated edge)
    monkeypatch.setattr(at, "LTF_ONLY", False)
    assert q("NVDA", "1d", "wave3", "long")[0] is True


def test_session_gate_defers_offhours_stocks(monkeypatch):
    """Stocks can only enter while NYSE is open; crypto is 24/7. Off-session
    stock signals are deferred (not opened this pass), not dropped."""
    # market closed
    monkeypatch.setattr(at, "market_status", lambda interval="1d": "closed")
    assert at.should_trade_ticker("BTC-USD", "1h")[0] is True      # crypto anytime
    assert at.should_trade_ticker("AMD", "1d")[0] is False         # stock deferred
    assert at.should_trade_ticker("AMD", "1h")[0] is False
    # market open
    monkeypatch.setattr(at, "market_status", lambda interval="1d": "open")
    assert at.should_trade_ticker("AMD", "1d")[0] is True
    assert at.should_trade_ticker("AMD", "1h")[0] is True
    # daily can also enter post-close (bar finalised), intraday cannot
    monkeypatch.setattr(at, "market_status", lambda interval="1d": "post_close")
    assert at.should_trade_ticker("AMD", "1d")[0] is True
    assert at.should_trade_ticker("AMD", "1h")[0] is False


def test_asset_class_of():
    # canonical function lives in strategy_system; auto_trader re-exports it
    assert asset_class_of("BTC-USD") == "crypto"
    assert asset_class_of("NVDA") == "stock"
    assert asset_class_of("ETH-USD") == "crypto"
    assert asset_class_of("INJ-USD") == "crypto"   # was mislabeled by old allowlist
    assert asset_class_of("FET-USD") == "crypto"   # was mislabeled by old allowlist
    # no -USD ticker should ever be "stock"
    sample_crypto = [
        "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "ADA-USD", "AVAX-USD",
        "LINK-USD", "DOT-USD", "NEAR-USD", "INJ-USD", "AAVE-USD", "ATOM-USD",
        "LTC-USD", "XLM-USD", "OP-USD", "HBAR-USD", "FIL-USD", "TRX-USD",
        "FET-USD", "SNX-USD", "UNI-USD", "DOGE-USD", "SHIB-USD", "ARB-USD",
    ]
    for tk in sample_crypto:
        assert asset_class_of(tk) == "crypto", f"{tk} should be crypto"
