"""Telegram signal notifications for Anton.

Sends a formatted message whenever the auto-trader opens a gate-passing paper
trade, so Anton can mirror it manually on the exchange. Every signal that
reaches here has already cleared: freshness, time-budget, the significance LUT
(robust setups only), and dedup — so this is an actionable, executable trade.

Outbound only (Bot API sendMessage) — no listener/webhook required. Silently
no-ops when TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID are absent (secrets live in
.env, never in code), so it is safe-by-default and never blocks trading.
"""
from __future__ import annotations

import html
import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
_TSTAT_FILE = ROOT / "brain-output" / "backtests" / "ewb_flat_alltf_grouped.parquet"
_TSTAT_CACHE: dict | None = None

# Real calendar hold per (interval, asset_class), measured from closed trades
# (stock 1h ≈ 3 trading days due to market hours; crypto 24/7 ≈ 1 day).
_HOLD = {
    ("1h", "crypto"): "~1 день", ("1h", "stock"): "~3 дня",
    ("4h", "crypto"): "~3 дня", ("4h", "stock"): "~1-2 недели",
    ("1d", "crypto"): "~3 недели", ("1d", "stock"): "~4 недели",
    ("1w", "crypto"): "~3-4 месяца", ("1w", "stock"): "~4 месяца",
}


def _token() -> str | None:
    return os.environ.get("TELEGRAM_BOT_TOKEN")


def _chat() -> str | None:
    return os.environ.get("TELEGRAM_CHAT_ID")


def enabled() -> bool:
    return bool(_token() and _chat())


def _asset_class(ticker: str) -> str:
    return "crypto" if str(ticker).upper().endswith("-USD") else "stock"


def _stars(tstat: float | None) -> str:
    """t-stat → 1..5 star confidence (significance under multiple testing)."""
    if tstat is None:
        return ""
    n = 5 if tstat >= 5 else 4 if tstat >= 3 else 3 if tstat >= 2 else 2
    return "★" * n + "☆" * (5 - n)


def _lookup_tstat(asset_class: str, interval: str, fig: str, side: str) -> float | None:
    global _TSTAT_CACHE
    if _TSTAT_CACHE is None:
        _TSTAT_CACHE = {}
        if _TSTAT_FILE.exists():
            try:
                import pandas as pd
                g = pd.read_parquet(_TSTAT_FILE)
                if "tstat" in g.columns:
                    for _, r in g.iterrows():
                        _TSTAT_CACHE[(str(r["asset_class"]), str(r["interval"]),
                                      str(r["fig_type"]), str(r["side"]))] = float(r["tstat"])
            except Exception:
                pass
    return _TSTAT_CACHE.get((asset_class, interval, fig, side))


def _tv_symbol(ticker: str) -> str:
    """TradingView symbol for the chart deep-link."""
    t = str(ticker or "").strip().upper()
    if ":" in t:
        return t
    if t.endswith("-USD"):
        return "CRYPTO:" + t.replace("-", "")
    return "NASDAQ:" + t


def format_signal(row: dict) -> str:
    """Render a signal_event row into the HTML Telegram message."""
    ticker = str(row.get("ticker", "?"))
    interval = str(row.get("interval", "?")).upper()
    side = str(row.get("side", "?")).lower()
    fig = str(row.get("fig_type", "?"))
    ac = _asset_class(ticker)
    entry = float(row.get("entry_px") or 0)
    stop = float(row.get("stop_px") or 0)
    target = float(row.get("target_px") or 0)
    p = float(row.get("probability") or 0)
    usd = float(row.get("trade_usd") or 0)

    is_long = side in ("long", "buy")
    head = "🟢 ПОКУПКА" if is_long else "🔴 ПРОДАЖА"
    risk = abs(entry - stop)
    reward = abs(target - entry)
    rr = (reward / risk) if risk > 0 else 0.0
    tp_pct = (reward / entry * 100) if entry else 0.0
    sl_pct = (risk / entry * 100) if entry else 0.0
    hold = _HOLD.get((interval.lower(), ac), "")
    stars = _stars(_lookup_tstat(ac, interval.lower(), fig, side if side in ("long", "short")
                                 else ("long" if is_long else "short")))

    def num(x):  # adaptive precision for crypto micro-prices
        return f"{x:,.2f}" if x >= 1 else f"{x:.6g}"

    e = html.escape
    lines = [
        f"<b>{head} · {e(ticker)} · {e(interval)}</b>",
        "",
        f"📐 Сетап: <b>{e(fig)}</b>",
    ]
    if stars:
        lines.append(f"📊 Надёжность: {stars}")
    lines += [
        "",
        f"💵 Вход:  <b>${num(entry)}</b>",
        f"🛑 Стоп:  ${num(stop)}  (−{sl_pct:.1f}%)" if is_long else f"🛑 Стоп:  ${num(stop)}  (+{sl_pct:.1f}%)",
        f"🎯 Тейк:  ${num(target)}  (+{tp_pct:.1f}%)" if is_long else f"🎯 Тейк:  ${num(target)}  (−{tp_pct:.1f}%)",
        f"⚖️ R:R = {rr:.2f}  ·  P(win) = {p:.0f}%",
        "",
        f"💰 Размер (Kelly): <b>${usd:,.0f}</b> на $10k",
    ]
    if hold:
        lines.append(f"⏱️ Удержание: {hold}")
    lines.append("")
    lines.append("<i>Сигнал прошёл значимость-гейт — исполним на бирже по цене входа.</i>")
    return "\n".join(lines)


def send_signal(row: dict, timeout: float = 10.0) -> bool:
    """POST the formatted signal to Anton's Telegram. Returns True on success,
    False (without raising) on any failure or when disabled."""
    if not enabled():
        return False
    text = format_signal(row)
    keyboard = {"inline_keyboard": [[
        {"text": "📊 График TradingView",
         "url": "https://www.tradingview.com/chart/?symbol=" + _tv_symbol(str(row.get("ticker", "")))},
    ]]}
    payload = json.dumps({
        "chat_id": _chat(),
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "reply_markup": keyboard,
    }).encode("utf-8")
    url = f"https://api.telegram.org/bot{_token()}/sendMessage"
    req = urllib.request.Request(url, data=payload,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            ok = json.load(resp).get("ok", False)
        if not ok:
            log.warning("telegram sendMessage returned ok=false")
        return bool(ok)
    except urllib.error.HTTPError as exc:
        try:
            exc.close()
        except Exception:
            pass
        log.warning("telegram HTTP %s", exc.code)
        return False
    except Exception as exc:  # never let a notify failure break trading
        log.warning("telegram send failed: %s", exc)
        return False
