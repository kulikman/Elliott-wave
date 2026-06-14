"""Tests for Telegram signal notifications."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # python/

from ewb import telegram_notify as tn  # noqa: E402


def _row(**over):
    base = {
        "ticker": "GE", "interval": "1w", "side": "long", "fig_type": "flat",
        "entry_px": 321.48, "stop_px": 265.65, "target_px": 411.81,
        "probability": 56.0, "trade_usd": 71.0,
    }
    base.update(over)
    return base


def test_disabled_without_creds(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    assert tn.enabled() is False
    # send is a safe no-op (no network, returns False) when disabled
    assert tn.send_signal(_row()) is False


def test_enabled_with_creds(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "y")
    assert tn.enabled() is True


def test_format_long_signal():
    msg = tn.format_signal(_row())
    assert "ПОКУПКА" in msg and "GE" in msg and "1W" in msg
    assert "$321.48" in msg            # entry
    assert "−17.4%" in msg             # stop pct below entry
    assert "+28.1%" in msg             # target pct above entry
    assert "R:R = 1.62" in msg
    assert "$71" in msg                # Kelly size
    assert "~4 месяца" in msg          # 1w hold


def test_format_short_signal():
    msg = tn.format_signal(_row(side="short", interval="4h", ticker="BTC-USD",
                                entry_px=64000, stop_px=68000, target_px=56000,
                                fig_type="flat", trade_usd=74))
    assert "ПРОДАЖА" in msg and "BTC-USD" in msg
    # for a short, stop is ABOVE entry (+), target BELOW (−)
    assert "🛑" in msg and "+6.2%" in msg
    assert "🎯" in msg and "−12.5%" in msg


def test_format_crypto_microprice():
    msg = tn.format_signal(_row(ticker="SHIB-USD", entry_px=2.4e-05,
                                stop_px=2.0e-05, target_px=3.2e-05, trade_usd=30))
    assert "SHIB-USD" in msg
    assert "2.4e-05" in msg            # adaptive precision, not $0.00


def test_tv_symbol():
    assert tn._tv_symbol("NVDA") == "NASDAQ:NVDA"
    assert tn._tv_symbol("BTC-USD") == "CRYPTO:BTCUSD"


def test_stars_by_tstat():
    assert tn._stars(8.2) == "★★★★★"
    assert tn._stars(3.5) == "★★★★☆"
    assert tn._stars(2.1) == "★★★☆☆"
    assert tn._stars(None) == ""
