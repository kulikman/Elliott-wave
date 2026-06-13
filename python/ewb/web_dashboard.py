"""Local web dashboard for the EWB strategy system."""
from __future__ import annotations

import json
import math
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

import pandas as pd
import yaml
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from ewb.strategy_system import (
    DEFAULT_BACKTEST_DIR,
    DEFAULT_FORWARD_LOG,
    append_jsonl,
    asset_class_of,
    forward_trades,
    is_crypto_ticker,
    note_event,
    outcome_event,
    probability_percent,
    read_jsonl,
    signal_event,
    signal_event_from_payload,
    trade_summary,
)


REPO = Path(__file__).resolve().parents[2]
SIGNALS_DIR = REPO / "brain-output" / "signals"
BACKTEST_DIR = REPO / DEFAULT_BACKTEST_DIR
FORWARD_LOG = REPO / DEFAULT_FORWARD_LOG
WATCHLIST = REPO / "configs" / "watchlist.yaml"
WATCHLIST_PROFILES = REPO / "configs" / "watchlist_profiles.yaml"
RISK_SETTINGS = REPO / "configs" / "risk_settings.yaml"
PORTFOLIO_FILE     = REPO / "brain-output" / "portfolio" / "holdings.json"
AUTO_TRADER_STATE  = REPO / "brain-output" / "auto_trader_state.json"
AUTO_TRADER_LOG    = REPO / "brain-output" / "auto_trader.log"
AUTO_TRADER_PID    = REPO / "brain-output" / "auto_trader.pid"
RETRAIN_EVERY      = 20


app = FastAPI(title="EWB Local Dashboard", version="0.1.0")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_watchlist() -> dict[str, Any]:
    if not WATCHLIST.exists():
        return {"stocks": [], "crypto": [], "intervals": ["1d", "4h", "1h"], "actions": ["buy", "sell"]}
    return yaml.safe_load(WATCHLIST.read_text(encoding="utf-8")) or {}


def wl_stocks(wl: dict) -> list[str]:
    """Return stocks list, supporting both new (stocks:) and legacy (tickers:) format."""
    if "stocks" in wl:
        return [str(t).upper() for t in wl.get("stocks", [])]
    tickers = [str(t).upper() for t in wl.get("tickers", [])]
    return [t for t in tickers if not any(t.endswith(s) for s in ("-USD", "-USDT", "-BTC", "-ETH", "-PERP"))]


def wl_crypto(wl: dict) -> list[str]:
    """Return crypto list, supporting both new (crypto:) and legacy (tickers:) format."""
    if "crypto" in wl:
        return [str(t).upper() for t in wl.get("crypto", [])]
    tickers = [str(t).upper() for t in wl.get("tickers", [])]
    return [t for t in tickers if any(t.endswith(s) for s in ("-USD", "-USDT", "-BTC", "-ETH", "-PERP"))]


def wl_all_tickers(wl: dict) -> list[str]:
    """All tickers combined."""
    return wl_stocks(wl) + wl_crypto(wl)


def wl_intervals(wl: dict) -> list[str]:
    """Return intervals list, supporting both new (intervals:) and legacy (interval:) format."""
    if "intervals" in wl:
        return [str(i) for i in wl.get("intervals", ["1d"])]
    return [str(wl.get("interval", "1d"))]


def write_watchlist(payload: dict[str, Any]) -> None:
    WATCHLIST.parent.mkdir(parents=True, exist_ok=True)
    WATCHLIST.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def read_profiles() -> dict[str, Any]:
    if not WATCHLIST_PROFILES.exists():
        return {"profiles": {}}
    return yaml.safe_load(WATCHLIST_PROFILES.read_text(encoding="utf-8")) or {"profiles": {}}


def read_risk_settings() -> dict[str, Any]:
    defaults = {"account_size": 10000.0, "risk_pct": 1.0, "max_position_pct": 25.0, "currency": "USD"}
    if not RISK_SETTINGS.exists():
        return defaults
    loaded = yaml.safe_load(RISK_SETTINGS.read_text(encoding="utf-8")) or {}
    return {**defaults, **loaded}


def write_risk_settings(payload: dict[str, Any]) -> None:
    RISK_SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    RISK_SETTINGS.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def write_profiles(payload: dict[str, Any]) -> None:
    WATCHLIST_PROFILES.parent.mkdir(parents=True, exist_ok=True)
    WATCHLIST_PROFILES.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def clean_watchlist_form(form: dict[str, str]) -> dict[str, Any]:
    tickers = [
        item.strip().upper()
        for item in form.get("tickers", "").replace("\n", ",").split(",")
        if item.strip()
    ]
    actions = [
        action.strip()
        for action in form.get("actions", "buy,sell").replace("\n", ",").split(",")
        if action.strip()
    ]
    return {
        "tickers": tickers,
        "interval": form.get("interval", "1h").strip() or "1h",
        "actions": actions or ["buy", "sell"],
        "fresh_hours": int(float(form.get("fresh_hours", "48") or 48)),
        "limit": int(float(form.get("limit", "20") or 20)),
    }


def clean_risk_form(form: dict[str, str]) -> dict[str, Any]:
    return {
        "account_size": float(form.get("account_size", "10000") or 10000),
        "risk_pct": float(form.get("risk_pct", "1") or 1),
        "max_position_pct": float(form.get("max_position_pct", "25") or 25),
        "currency": form.get("currency", "USD").strip().upper() or "USD",
    }


def fmt(value: Any, digits: int = 2) -> str:
    if value in (None, ""):
        return "-"
    try:
        number = float(value)
    except Exception:
        return str(value)
    if not math.isfinite(number):
        return "-"
    return f"{number:.{digits}f}"


def pct(value: Any) -> str:
    if value in (None, ""):
        return "-"
    try:
        number = float(value)
    except Exception:
        return str(value)
    if not math.isfinite(number):
        return "-"
    return f"{number * 100:.1f}%"


def probability_label(value: Any) -> str:
    prob = probability_percent(value)
    return "-" if prob is None else f"{prob:.1f}%"


def price(value: Any) -> str:
    if value in (None, "") or pd.isna(value):
        return "-"
    try:
        return f"{float(value):.6g}"
    except Exception:
        return str(value)


def html_escape(value: Any) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def nav(active: str) -> str:
    items = [
        ("Главная", "Dashboard", "/"),
        ("Доска действий", "Action Board", "/action-board"),
        ("Сигналы", "Signals", "/signals"),
        ("Сделки", "Trades", "/trades"),
        ("Портфель", "Portfolio", "/portfolio"),
        ("Настройки", "Settings", "/settings"),
    ]
    links = []
    for label, key, href in items:
        cls = "active" if key == active else ""
        links.append(f'<a class="{cls}" href="{href}">{label}</a>')
    return "".join(links)


def layout(title: str, active: str, body: str) -> HTMLResponse:
    html = f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html_escape(title)}</title>
  <style>
    :root {{
      --bg: #f6f7f9;
      --surface: #ffffff;
      --text: #17202a;
      --muted: #667085;
      --line: #d9dee7;
      --green: #087443;
      --red: #b42318;
      --amber: #a15c07;
      --blue: #175cd3;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: var(--bg); color: var(--text); }}
    header {{ display: flex; align-items: center; justify-content: space-between; gap: 20px; padding: 18px 28px; background: #101828; color: white; }}
    header h1 {{ font-size: 18px; margin: 0; font-weight: 650; letter-spacing: 0; }}
    nav {{ display: flex; flex-wrap: wrap; gap: 6px; }}
    nav a {{ color: #d0d5dd; text-decoration: none; padding: 8px 10px; border-radius: 6px; font-size: 14px; }}
    nav a.active, nav a:hover {{ background: #344054; color: white; }}
    main {{ max-width: 1440px; margin: 0 auto; padding: 24px 28px 48px; }}
    .topbar {{ display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 18px; }}
    h2 {{ margin: 0; font-size: 24px; letter-spacing: 0; }}
    h3 {{ margin: 26px 0 10px; font-size: 16px; }}
    .muted {{ color: var(--muted); }}
    .grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }}
    .metric {{ background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 14px; min-height: 92px; }}
    .metric .label {{ color: var(--muted); font-size: 13px; }}
    .metric .value {{ margin-top: 8px; font-size: 24px; font-weight: 700; }}
    .band {{ background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 16px; margin: 14px 0; }}
    table {{ width: 100%; border-collapse: collapse; background: var(--surface); border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid var(--line); text-align: left; font-size: 14px; vertical-align: top; }}
    th {{ color: #344054; background: #eef2f6; font-weight: 650; }}
    tr:last-child td {{ border-bottom: 0; }}
    .pill {{ display: inline-flex; align-items: center; min-height: 24px; padding: 3px 8px; border-radius: 999px; font-size: 12px; font-weight: 650; background: #eef2f6; color: #344054; }}
    .buy, .long, .win, .ready, .review {{ background: #dcfae6; color: var(--green); }}
    .sell, .short, .loss, .block {{ background: #fee4e2; color: var(--red); }}
    .observe, .paper, .wait, .open, .check, .watch {{ background: #fef0c7; color: var(--amber); }}
    .btn {{ border: 1px solid #175cd3; background: #175cd3; color: white; border-radius: 6px; padding: 9px 12px; cursor: pointer; font-weight: 650; }}
    .btn.secondary {{ background: white; color: #175cd3; }}
    .btn.mini {{ display: inline-flex; width: auto; padding: 5px 8px; margin: 2px 3px 2px 0; font-size: 12px; text-decoration: none; }}
    form.inline {{ display: inline; }}
    input, select {{ width: 100%; border: 1px solid var(--line); border-radius: 6px; padding: 9px 10px; font: inherit; }}
    .form-grid {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; align-items: end; }}
    .code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; }}
    @media (max-width: 900px) {{ header {{ align-items: flex-start; flex-direction: column; }} .grid, .form-grid {{ grid-template-columns: 1fr; }} main {{ padding: 18px; }} table {{ display: block; overflow-x: auto; }} }}
  </style>
</head>
<body>
  <header><h1>EWB — Система стратегии</h1><nav>{nav(active)}</nav></header>
  <main>{body}</main>
</body>
</html>"""
    return HTMLResponse(html)


_DECISION_RU = {
    "review": "ПРОВЕРИТЬ", "hold": "ДЕРЖАТЬ", "check": "СВЕРИТЬ",
    "watch": "НАБЛЮДАТЬ", "wait": "ЖДАТЬ", "observe": "НАБЛЮДЕНИЕ",
    "buy": "ПОКУПКА", "sell": "ПРОДАЖА", "long": "ЛОНГ", "short": "ШОРТ",
    "open": "открыта", "closed": "закрыта", "win": "профит", "loss": "убыток",
    "ok": "ОК", "ready": "готов",
}


def decision_pill(value: Any) -> str:
    """Pill with Russian label but English CSS class for consistent colours."""
    key = str(value).lower().split()[0] if value not in (None, "") else ""
    label = _DECISION_RU.get(key, str(value))
    return pill(label, key)


def pill(value: Any, cls: str | None = None) -> str:
    text = html_escape(value if value not in (None, "") else "-")
    css = cls or str(value).lower().replace(" ", "-")
    return f'<span class="pill {html_escape(css)}">{text}</span>'


def table(headers: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        return '<div class="band muted">No rows yet.</div>'
    head = "".join(f"<th>{html_escape(col)}</th>" for col in headers)
    body_rows = []
    for row in rows:
        body_rows.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"


def as_timestamp(value: Any) -> pd.Timestamp | None:
    if value in (None, ""):
        return None
    try:
        ts = pd.Timestamp(value)
    except Exception:
        return None
    if pd.isna(ts):
        return None
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts.tz_convert("UTC")


def age_text(value: Any) -> str:
    ts = as_timestamp(value)
    if ts is None:
        return "-"
    age_hours = max(0.0, (pd.Timestamp.now("UTC") - ts).total_seconds() / 3600.0)
    if age_hours < 48:
        return f"{age_hours:.0f}ч"
    return f"{age_hours / 24.0:.1f}д"


def dt_text(value: Any) -> str:
    """Format an event timestamp as 'YYYY-MM-DD HH:MM' (UTC) for the trade log."""
    ts = as_timestamp(value)
    if ts is None:
        return "-"
    return ts.strftime("%Y-%m-%d %H:%M")


def seq_numbers(frame: pd.DataFrame) -> dict[str, int]:
    """Stable per-trade sequence number (1,2,3…) ordered by entry time.

    Numbering spans open + closed trades so an ID never changes when a trade
    moves from the open tab to history."""
    if frame.empty or "signal_id" not in frame.columns:
        return {}
    sort_col = "entry_ts" if "entry_ts" in frame.columns else "recorded_at"
    ordered = frame.sort_values(sort_col, ascending=True, na_position="first")
    return {str(sid): i for i, sid in enumerate(ordered["signal_id"].tolist(), start=1)}


def rr_value(entry: Any, stop: Any, target: Any) -> float | None:
    try:
        entry_f = float(entry)
        stop_f = float(stop)
        target_f = float(target)
    except Exception:
        return None
    risk = abs(entry_f - stop_f)
    reward = abs(target_f - entry_f)
    return reward / risk if risk > 0 else None


def rr_text(entry: Any, stop: Any, target: Any) -> str:
    rr = rr_value(entry, stop, target)
    return "-" if rr is None else f"{rr:.2f}"


def position_plan(
    *,
    entry: Any,
    stop: Any,
    target: Any,
    side: str,
    settings: dict[str, Any] | None = None,
    size_mult: float = 1.0,
) -> dict[str, Any]:
    settings = settings or read_risk_settings()
    try:
        entry_f = float(entry)
        stop_f = float(stop)
        target_f = float(target)
        account = float(settings.get("account_size", 0))
        risk_pct = float(settings.get("risk_pct", 0))
        max_position_pct = float(settings.get("max_position_pct", 100))
    except Exception:
        return {"ok": False}
    if entry_f <= 0 or account <= 0:
        return {"ok": False}
    direction = 1 if str(side).lower() in {"buy", "long"} else -1
    risk_per_unit = direction * (entry_f - stop_f)
    reward_per_unit = direction * (target_f - entry_f)
    if risk_per_unit <= 0 or reward_per_unit <= 0:
        return {"ok": False}
    # EV-weighted sizing: scale risk by the setup's edge multiplier (0.5x..2x).
    try:
        mult = max(0.25, min(2.0, float(size_mult)))
    except Exception:
        mult = 1.0
    risk_cash = account * risk_pct / 100.0 * mult
    max_position_cash = account * max_position_pct / 100.0
    qty_by_risk = risk_cash / risk_per_unit
    qty_by_cap = max_position_cash / entry_f
    qty = max(0.0, min(qty_by_risk, qty_by_cap))
    capital = qty * entry_f
    actual_risk = qty * risk_per_unit
    reward_cash = qty * reward_per_unit
    return {
        "ok": True,
        "qty": qty,
        "capital": capital,
        "risk_cash": actual_risk,
        "reward_cash": reward_cash,
        "rr": reward_per_unit / risk_per_unit,
        "risk_cap_limited": qty_by_cap < qty_by_risk,
        "size_mult": mult,
        "currency": settings.get("currency", "USD"),
    }


def money(value: Any, currency: str = "USD") -> str:
    try:
        number = float(value)
    except Exception:
        return "-"
    if not math.isfinite(number):
        return "-"
    return f"{number:,.2f} {currency}"


def qty_text(value: Any) -> str:
    try:
        number = float(value)
    except Exception:
        return "-"
    if not math.isfinite(number):
        return "-"
    return f"{number:.6g}"


def tv_symbol(ticker: str) -> str:
    ticker = str(ticker or "").strip().upper()
    if ":" in ticker:
        return ticker
    if is_crypto_ticker(ticker):
        compact = ticker.replace("-", "").replace("/", "").replace("_", "")
        if compact.endswith(("USDT", "USDC")):
            return "BINANCE:" + compact
        if compact.endswith("USD"):
            return "CRYPTO:" + compact
        return "CRYPTO:" + compact + "USD"
    return "NASDAQ:" + ticker


def tradingview_link(ticker: Any) -> str:
    ticker_text = str(ticker or "")
    if not ticker_text:
        return "-"
    href = "https://www.tradingview.com/chart/?symbol=" + tv_symbol(ticker_text)
    return f'<a class="btn secondary mini" href="{html_escape(href)}" target="_blank">TV</a>'


def action_decision(action: str, probability: Any, rr: float | None, entry_ts: Any) -> tuple[str, str]:
    action = str(action).lower()
    if action in {"long", "enter long"}:
        action = "buy"
    elif action in {"short", "enter short"}:
        action = "sell"
    if action not in {"buy", "sell"}:
        return "WAIT", "Нет торговой стороны"
    prob = probability_percent(probability)
    age = as_timestamp(entry_ts)
    age_hours = None if age is None else max(0.0, (pd.Timestamp.now("UTC") - age).total_seconds() / 3600.0)
    if rr is None or rr < 1.0:
        return "WAIT", "RR ниже 1.0 или отсутствует"
    if prob is None or prob < 55.0:
        return "WATCH", "Вероятность ниже 55%"
    if age_hours is not None and age_hours > 72:
        return "CHECK", "Сигнал старше 72ч"
    return "REVIEW", "Проверьте график, HTF-контекст и новости"


def accept_signal_form(signal: dict[str, Any]) -> str:
    risk = signal.get("risk_box", {})
    fields = {
        "ticker": signal.get("ticker", ""),
        "interval": signal.get("interval", ""),
        "action": signal.get("recommended_action", ""),
        "entry_ts": signal.get("entry_ts", ""),
        "entry_px": risk.get("entry_px", ""),
        "stop_px": risk.get("stop_px", ""),
        "target_px": risk.get("target_px", ""),
        "fig_type": signal.get("pattern", ""),
        "probability": signal.get("p_trade_win", ""),
        "htf_context": "scanner signal - confirm HTF on chart",
    }
    inputs = "".join(
        f'<input type="hidden" name="{html_escape(key)}" value="{html_escape(value)}">'
        for key, value in fields.items()
        if value not in (None, "")
    )
    return f'<form class="inline" method="post" action="/signals/accept">{inputs}<button class="btn mini" type="submit">В бумаги</button></form>'


def asset_class(ticker: Any) -> str:
    return asset_class_of(ticker)


def passes_action_filters(
    *,
    decision: str,
    ticker: Any,
    interval: Any,
    probability: Any,
    rr: float | None,
    filters: dict[str, Any],
) -> bool:
    decision_filter = filters.get("decision", "all")
    asset_filter = filters.get("asset", "all")
    tf_filter = filters.get("tf", "all")
    min_p = float(filters.get("min_p") or 0)
    min_rr = float(filters.get("min_rr") or 0)
    prob = probability_percent(probability)
    if decision_filter != "all" and decision.lower() != decision_filter:
        return False
    if asset_filter != "all" and asset_class(ticker) != asset_filter:
        return False
    if tf_filter != "all" and str(interval) != tf_filter:
        return False
    if min_p and (prob is None or prob < min_p):
        return False
    if min_rr and (rr is None or rr < min_rr):
        return False
    return True


def action_board_rows(limit: int = 20, filters: dict[str, Any] | None = None) -> list[list[Any]]:
    filters = filters or {}
    report = read_json(SIGNALS_DIR / "daily_report.json")
    risk_settings = read_risk_settings()
    forward = forward_frame()
    seq = seq_numbers(forward)
    rows: list[list[Any]] = []
    for signal in report.get("signals", [])[:limit]:
        action = str(signal.get("recommended_action", "wait")).lower()
        risk = signal.get("risk_box", {})
        rr = rr_value(risk.get("entry_px"), risk.get("stop_px"), risk.get("target_px"))
        decision, reason = action_decision(action, signal.get("p_trade_win"), rr, signal.get("entry_ts"))
        if not passes_action_filters(
            decision=decision,
            ticker=signal.get("ticker", ""),
            interval=signal.get("interval", report.get("interval", "")),
            probability=signal.get("p_trade_win"),
            rr=rr,
            filters=filters,
        ):
            continue
        plan = position_plan(
            entry=risk.get("entry_px"),
            stop=risk.get("stop_px"),
            target=risk.get("target_px"),
            side=action,
            settings=risk_settings,
        )
        action_cell = tradingview_link(signal.get("ticker", "")) + accept_signal_form(signal)
        rows.append([
            '<span class="muted">—</span>',
            decision_pill(decision),
            html_escape(signal.get("ticker", "")),
            decision_pill(action),
            html_escape(signal.get("interval", report.get("interval", ""))),
            html_escape(signal.get("pattern", "")),
            probability_label(signal.get("p_trade_win")),
            "-" if rr is None else f"{rr:.2f}",
            qty_text(plan.get("qty")) if plan.get("ok") else "-",
            money(plan.get("risk_cash"), plan.get("currency", "USD")) if plan.get("ok") else "-",
            price(risk.get("entry_px")),
            price(risk.get("stop_px")),
            price(risk.get("target_px")),
            age_text(signal.get("entry_ts")),
            action_cell + f'<div class="muted">{html_escape(reason)}</div>',
        ])
    open_trades = forward[forward["status"] == "open"].copy() if not forward.empty else pd.DataFrame()
    sort_col = "entry_ts" if "entry_ts" in open_trades.columns else None
    sorted_open = open_trades.sort_values(sort_col, ascending=False) if sort_col else open_trades
    for _, row in sorted_open.iterrows():
        sid = str(row.get("signal_id", ""))
        signal_id = html_escape(sid)
        num = seq.get(sid, "")
        rr = rr_value(row.get("entry_px"), row.get("stop_px"), row.get("target_px"))
        if not passes_action_filters(
            decision="HOLD",
            ticker=row.get("ticker", ""),
            interval=row.get("interval", ""),
            probability=row.get("probability", ""),
            rr=rr,
            filters=filters,
        ):
            continue
        plan = position_plan(
            entry=row.get("entry_px"),
            stop=row.get("stop_px"),
            target=row.get("target_px"),
            side=row.get("side", ""),
            settings=risk_settings,
            size_mult=row.get("size_mult", 1.0),
        )
        rows.insert(0, [
            f'<a class="code" href="/trades/{signal_id}" title="{signal_id}"><strong>{num}</strong></a>',
            pill("ДЕРЖАТЬ", "open"),
            html_escape(row.get("ticker", "")),
            decision_pill(row.get("side", "")),
            html_escape(row.get("interval", "")),
            html_escape(row.get("fig_type", "")),
            probability_label(row.get("probability")),
            "-" if rr is None else f"{rr:.2f}",
            qty_text(plan.get("qty")) if plan.get("ok") else "-",
            money(plan.get("risk_cash"), plan.get("currency", "USD")) if plan.get("ok") else "-",
            price(row.get("entry_px")),
            price(row.get("stop_px")),
            price(row.get("target_px")),
            age_text(row.get("entry_ts")),
            tradingview_link(row.get("ticker", "")) + f'<a class="btn mini" href="/trades/{signal_id}">Управление</a>',
        ])
    return rows[:limit]


def checklist_rows(signal: dict[str, Any], outcome: dict[str, Any] | None) -> list[list[Any]]:
    rr = rr_value(signal.get("entry_px"), signal.get("stop_px"), signal.get("target_px"))
    action = str(signal.get("action", signal.get("side", "wait"))).lower()
    decision, reason = action_decision(action, signal.get("probability"), rr, signal.get("entry_ts"))
    prob = probability_percent(signal.get("probability"))
    return [
        ["Статус сделки", pill("ЗАКРЫТА" if outcome else "ОТКРЫТА", "open" if not outcome else "ready")],
        ["Решение", decision_pill(decision)],
        ["Причина", html_escape(reason)],
        ["Свежесть", age_text(signal.get("entry_ts"))],
        ["Порог вероятности", pill("ОК" if prob is not None and prob >= 55.0 else "СВЕРИТЬ", "review" if prob is not None and prob >= 55.0 else "check")],
        ["Порог R:R", pill("ОК" if rr is not None and rr >= 1.0 else "СВЕРИТЬ", "review" if rr is not None and rr >= 1.0 else "check")],
        ["HTF контекст", html_escape(signal.get("htf_context", "") or "Проверьте график вручную")],
        ["График", tradingview_link(signal.get("ticker", ""))],
        ["Ручная проверка", "Перед входом проверьте новости, ликвидность, дату отчётности и размер позиции."],
    ]


def risk_plan_rows(signal: dict[str, Any]) -> list[list[Any]]:
    plan = position_plan(
        entry=signal.get("entry_px"),
        stop=signal.get("stop_px"),
        target=signal.get("target_px"),
        side=signal.get("action", signal.get("side", "")),
        size_mult=signal.get("size_mult", 1.0),
    )
    if not plan.get("ok"):
        return [["План позиции", "Нет или некорректны вход/SL/TP. Пока не рассчитывайте размер."]]
    currency = plan.get("currency", "USD")
    return [
        ["Количество", qty_text(plan.get("qty"))],
        ["Множитель размера (по EV)", f"{plan.get('size_mult', 1.0):.2f}x"],
        ["Задействовано капитала", money(plan.get("capital"), currency)],
        ["Риск", money(plan.get("risk_cash"), currency)],
        ["Потенциальная прибыль", money(plan.get("reward_cash"), currency)],
        ["R:R", fmt(plan.get("rr"))],
        ["Лимит капитала", "Применён максимум на позицию" if plan.get("risk_cap_limited") else "Размер ограничен % риска"],
    ]


def forward_frame() -> pd.DataFrame:
    return forward_trades(read_jsonl(FORWARD_LOG))


def alert_event_rows(limit: int = 30) -> list[list[Any]]:
    # Dedupe by signal_id (the log can hold the same signal twice); keep the
    # latest occurrence so the feed mirrors the deduped trade list.
    by_id: dict[str, dict[str, Any]] = {}
    for row in read_jsonl(FORWARD_LOG):
        if row.get("event_type") == "signal":
            by_id[str(row.get("signal_id", ""))] = row
    signals = list(by_id.values())
    seq = seq_numbers(forward_frame())
    rows = []
    for row in reversed(signals[-limit:]):
        sid = str(row.get("signal_id", ""))
        signal_id = html_escape(sid)
        num = seq.get(sid, "")
        rows.append([
            f'<a class="code" href="/trades/{signal_id}" title="{signal_id}"><strong>{num}</strong></a>',
            html_escape(row.get("ticker", "")),
            html_escape(row.get("interval", "")),
            decision_pill(row.get("side", "")),
            html_escape(row.get("fig_type", "")),
            price(row.get("entry_px")),
            price(row.get("stop_px")),
            price(row.get("target_px")),
            probability_label(row.get("probability")),
            html_escape(row.get("source", "")),
            dt_text(row.get("recorded_at", "")),
        ])
    return rows


def events_for_signal(signal_id: str) -> list[dict[str, Any]]:
    return [
        row
        for row in read_jsonl(FORWARD_LOG)
        if row.get("signal_id") == signal_id
    ]


def signal_detail(signal_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None, list[dict[str, Any]]]:
    signal = None
    outcome = None
    notes = []
    for row in events_for_signal(signal_id):
        if row.get("event_type") == "signal":
            signal = row
        elif row.get("event_type") == "outcome":
            outcome = row
        elif row.get("event_type") == "note":
            notes.append(row)
    return signal, outcome, notes


def dashboard_payload() -> dict[str, Any]:
    forward = forward_frame()
    open_trades = forward[forward["status"] == "open"].copy() if not forward.empty else pd.DataFrame()
    closed = forward[forward["status"] == "closed"].copy() if not forward.empty else pd.DataFrame()
    daily = read_json(BACKTEST_DIR / "ewb_forward_daily_report.json")
    backtest = read_json(BACKTEST_DIR / "ewb_strategy_backtest_summary.json")
    forward_summary = trade_summary(closed)
    return {
        "daily": daily,
        "backtest": backtest,
        "forward": forward,
        "open": open_trades,
        "closed": closed,
        "forward_summary": forward_summary,
    }


def forward_vs_backtest_rows() -> list[list[Any]]:
    """Per tradeable setup: backtest WR/EV/n (OOS LUT) vs live forward closed
    WR/EV/n — the real check that the validated edge holds out of sample."""
    from ewb.auto_trader import (load_setup_winrates, asset_class_of,
                                 SETUP_EV_FLOOR, SETUP_WR_FLOOR, SETUP_MIN_N)
    lut = load_setup_winrates()
    closed = forward_frame()
    closed = closed[closed["status"] == "closed"].copy() if not closed.empty else pd.DataFrame()
    fgrp: dict = {}
    if not closed.empty and "net_ret" in closed.columns:
        closed["asset_class"] = closed["ticker"].apply(asset_class_of)
        for key, g in closed.groupby(["asset_class", "interval", "fig_type", "side"]):
            fgrp[tuple(key)] = (float(g["win"].mean()), int(len(g)), float(g["net_ret"].mean()))
    rows: list[list[Any]] = []
    for key, (wr, n, ev) in sorted(lut.items(), key=lambda x: -x[1][2]):
        ac, iv, fig, side = key
        tradeable = ev >= SETUP_EV_FLOOR and wr >= SETUP_WR_FLOOR and n >= SETUP_MIN_N
        fwr, fn, fev = fgrp.get(key, (None, 0, None))
        if not tradeable and not fn:
            continue
        bt = f"{wr*100:.0f}% / {ev*100:+.2f}% / n{n}"
        if fn:
            fw = f"{fwr*100:.0f}% / {fev*100:+.2f}% / n{fn}"
            verdict = pill("держится", "win") if (fev - ev) >= -0.005 else pill("просел", "loss")
        else:
            fw = '<span class="muted">— нет закрытых —</span>'
            verdict = '<span class="muted">ждём</span>'
        rows.append([f"{html_escape(ac)}/{iv}/{html_escape(fig)}/{side}", bt, fw, verdict])
    return rows


@app.get("/", response_class=HTMLResponse)
def dashboard() -> HTMLResponse:
    data = dashboard_payload()
    daily = data["daily"]
    backtest = data["backtest"]
    decision = daily.get("decision", "OBSERVE")
    counts = daily.get("counts", {})
    portfolio = backtest.get("portfolio", {})
    metrics = [
        ("Решение", decision_pill(decision)),
        ("Открытых сделок", counts.get("open", len(data["open"]))),
        ("Закрыто (forward)", counts.get("closed", len(data["closed"]))),
        ("Винрейт (бэктест)", pct(portfolio.get("winrate"))),
        ("Ожидание (бэктест)", pct(portfolio.get("expectancy"))),
        ("Винрейт (forward)", pct(data["forward_summary"].get("winrate"))),
        ("Ожидание (forward)", pct(data["forward_summary"].get("expectancy"))),
        ("PF (forward)", fmt(data["forward_summary"].get("profit_factor"))),
    ]
    metric_html = "".join(
        f'<div class="metric"><div class="label">{html_escape(label)}</div><div class="value">{value}</div></div>'
        for label, value in metrics
    )
    body = f"""
    <div class="topbar">
      <div><h2>Главная</h2><div class="muted">Локальный центр управления сигналами, бумажной торговлей и forward-валидацией.</div></div>
      <form method="post" action="/actions/run-strategy"><button class="btn" type="submit">Запустить пайплайн</button></form>
    </div>
    <div class="grid">{metric_html}</div>
    <div class="band"><strong>Рабочее решение:</strong> {html_escape(daily.get("decision_reason", "Запустите пайплайн стратегии, чтобы получить свежее решение."))}</div>
    <h3>Доска действий</h3>
    {table(["#", "Решение", "Тикер", "Сторона", "ТФ", "Паттерн", "P", "RR", "Кол-во", "Риск", "Вход", "SL", "TP", "Возраст", "Действие"], action_board_rows(12))}
    <h3>Авто-трейдер</h3>
    {auto_trader_widget()}
    <h3>Форвард vs Бэктест</h3>
    {table(["Сетап", "Бэктест WR/EV/n", "Форвард WR/EV/n", "Вердикт"], forward_vs_backtest_rows())}
    <div class="band muted" style="margin-top:0">Главная проверка: держится ли живой edge к OOS-бэктесту. «Вердикт» по сетапу появляется, когда по нему закроются форвард-сделки (EV-просадка &gt; 0.5% → «просел»).</div>
    <h3>Что дальше</h3>
    <div class="band">
      1. Авто-трейдер открывает/закрывает бумажные сделки автономно.<br>
      2. Следи за результатами на вкладке «Сделки».<br>
      3. После {RETRAIN_EVERY} закрытых сделок — модель переобучается автоматически.
    </div>
    """
    return layout("Главная", "Dashboard", body)


@app.get("/action-board", response_class=HTMLResponse)
def action_board(
    decision: str = "all",
    asset: str = "all",
    tf: str = "all",
    min_p: float = 0,
    min_rr: float = 0,
) -> HTMLResponse:
    filters = {"decision": decision, "asset": asset, "tf": tf, "min_p": min_p, "min_rr": min_rr}
    body = f"""
    <div class="topbar"><div><h2>Доска действий</h2><div class="muted">Первый экран для торговых решений: что проверить, держать, пропустить или закрыть.</div></div></div>
    <form class="band form-grid" method="get" action="/action-board">
      <label>Решение<select name="decision">
        <option value="all" {"selected" if decision == "all" else ""}>Все</option>
        <option value="review" {"selected" if decision == "review" else ""}>ПРОВЕРИТЬ</option>
        <option value="hold" {"selected" if decision == "hold" else ""}>ДЕРЖАТЬ</option>
        <option value="check" {"selected" if decision == "check" else ""}>СВЕРИТЬ</option>
        <option value="watch" {"selected" if decision == "watch" else ""}>НАБЛЮДАТЬ</option>
      </select></label>
      <label>Актив<select name="asset">
        <option value="all" {"selected" if asset == "all" else ""}>Все</option>
        <option value="stock" {"selected" if asset == "stock" else ""}>Акции</option>
        <option value="crypto" {"selected" if asset == "crypto" else ""}>Крипто</option>
      </select></label>
      <label>ТФ<input name="tf" value="{html_escape(tf)}" placeholder="все, 1h, 4h, 1d"></label>
      <label>Мин. P<input name="min_p" value="{html_escape(min_p)}" placeholder="55"></label>
      <label>Мин. RR<input name="min_rr" value="{html_escape(min_rr)}" placeholder="1.0"></label>
      <button class="btn" type="submit">Фильтр</button>
    </form>
    {table(["#", "Решение", "Тикер", "Сторона", "ТФ", "Паттерн", "P", "RR", "Кол-во", "Риск", "Вход", "SL", "TP", "Возраст", "Действие"], action_board_rows(50, filters))}
    <div class="band">
      <strong>Как читать:</strong> ПРОВЕРИТЬ — открыть график и подтвердить HTF/волновой контекст перед входом.
      ДЕРЖАТЬ — есть открытая forward-сделка для управления. НАБЛЮДАТЬ/СВЕРИТЬ — не входить без ручной проверки.
    </div>
    """
    return layout("Доска действий", "Action Board", body)


@app.get("/signals", response_class=HTMLResponse)
def signals() -> HTMLResponse:
    report = read_json(SIGNALS_DIR / "daily_report.json")
    signals = report.get("signals", [])
    rows = []
    for signal in signals:
        risk = signal.get("risk_box", {})
        rr = rr_text(risk.get("entry_px"), risk.get("stop_px"), risk.get("target_px"))
        rows.append([
            html_escape(signal.get("ticker", "")),
            decision_pill(signal.get("recommended_action", "wait")),
            html_escape(signal.get("pattern", "")),
            probability_label(signal.get("p_trade_win")),
            pct(signal.get("expected_net_return")),
            rr,
            price(risk.get("entry_px")),
            price(risk.get("stop_px")),
            price(risk.get("target_px")),
            age_text(signal.get("entry_ts")),
            tradingview_link(signal.get("ticker", "")),
            dt_text(signal.get("entry_ts")),
        ])
    body = f"""
    <div class="topbar"><div><h2>Сигналы</h2><div class="muted">Свежие сигналы сканера по выбранному вотчлисту.</div></div></div>
    {table(["Тикер", "Действие", "Паттерн", "P(win)", "EV", "RR", "Вход", "SL", "TP", "Возраст", "График", "Время"], rows)}
    <h3>Лента алертов</h3>
    {table(["ID", "Тикер", "ТФ", "Сторона", "Паттерн", "Вход", "SL", "TP", "P", "Источник", "Записано"], alert_event_rows())}
    """
    return layout("Сигналы", "Signals", body)


def trade_rows(frame: pd.DataFrame, include_settle: bool,
               seq: dict[str, int] | None = None) -> list[list[Any]]:
    if frame.empty:
        return []
    seq = seq or {}
    sort_col = "entry_ts" if "entry_ts" in frame.columns else frame.columns[0]
    rows = []
    for _, row in frame.sort_values(sort_col, ascending=False).iterrows():
        sid = str(row.get("signal_id", ""))
        signal_id = html_escape(sid)
        num = seq.get(sid, "")
        id_cell = f'<a class="code" href="/trades/{signal_id}" title="{signal_id}"><strong>{num}</strong></a>'
        if include_settle:
            settle = f"""
            <form class="inline" method="post" action="/trades/settle">
              <input type="hidden" name="signal_id" value="{signal_id}">
              <input type="hidden" name="exit_ts" value="{pd.Timestamp.now("UTC").isoformat()}">
              <input type="hidden" name="exit_px" value="{html_escape(row.get("target_px", ""))}">
              <input type="hidden" name="exit_reason" value="tp">
              <button class="btn secondary" type="submit">TP</button>
            </form>
            """
            rows.append([
                id_cell,
                html_escape(row.get("ticker", "")),
                html_escape(row.get("interval", "")),
                decision_pill(row.get("side", "")),
                html_escape(row.get("fig_type", "")),
                price(row.get("entry_px")),
                dt_text(row.get("entry_ts")),
                price(row.get("stop_px")),
                price(row.get("target_px")),
                pill("открыта", "open"),
                settle,
            ])
        else:
            rows.append([
                id_cell,
                html_escape(row.get("ticker", "")),
                html_escape(row.get("interval", "")),
                decision_pill(row.get("side", "")),
                html_escape(row.get("fig_type", "")),
                price(row.get("entry_px")),
                dt_text(row.get("entry_ts")),
                price(row.get("exit_px")),
                dt_text(row.get("exit_ts")),
                html_escape(row.get("exit_reason", "")),
                pct(row.get("net_ret")),
            ])
    return rows


@app.get("/trades", response_class=HTMLResponse)
def trades(tab: str = "open") -> HTMLResponse:
    frame = forward_frame()
    seq = seq_numbers(frame)
    open_trades  = frame[frame["status"] == "open"].copy()   if not frame.empty else pd.DataFrame()
    closed_trades = frame[frame["status"] == "closed"].copy() if not frame.empty else pd.DataFrame()

    tab_open_cls   = "tab-btn active" if tab == "open"    else "tab-btn"
    tab_hist_cls   = "tab-btn active" if tab == "history" else "tab-btn"

    if tab == "history":
        tab_content = table(
            ["#", "Тикер", "ТФ", "Сторона", "Паттерн", "Вход", "Время входа",
             "Выход", "Время выхода", "Причина", "Доходность"],
            trade_rows(closed_trades, False, seq),
        )
    else:
        tab_content = f"""
        {table(["#", "Тикер", "ТФ", "Сторона", "Паттерн", "Вход", "Время входа",
                "SL", "TP", "Статус", "Быстро"],
               trade_rows(open_trades, True, seq))}
        <h3 style="margin:1.5rem 0 .5rem">Закрыть вручную</h3>
        <form class="band form-grid" method="post" action="/trades/settle">
          <label>Signal ID<input name="signal_id" required></label>
          <label>Время выхода<input name="exit_ts" placeholder="2026-06-07T16:00:00Z" required></label>
          <label>Цена выхода<input name="exit_px" required></label>
          <label>Причина<select name="exit_reason">
            <option>tp</option><option>sl</option><option>time</option>
            <option>manual</option><option>cancelled</option>
          </select></label>
          <button class="btn" type="submit">Закрыть</button>
        </form>"""

    open_cnt   = len(open_trades)
    closed_cnt = len(closed_trades)

    body = f"""
    <div class="topbar"><div><h2>Сделки</h2>
      <div class="muted">Бумажные позиции — открытые и история. № — порядковый номер сделки.</div>
    </div></div>
    <div style="display:flex;gap:.5rem;margin:1rem 1.5rem .5rem;border-bottom:1px solid #2a2e39;">
      <a href="/trades?tab=open"
         class="{tab_open_cls}"
         style="padding:.5rem 1.2rem;text-decoration:none;font-weight:600;
                border-bottom:{'3px solid #2962ff' if tab=='open' else '3px solid transparent'};
                color:{'#fff' if tab=='open' else '#9ba3af'};">
        Открытые <span style="background:#2962ff22;color:#2962ff;border-radius:9px;
                              padding:1px 8px;font-size:.75rem;margin-left:4px;">{open_cnt}</span>
      </a>
      <a href="/trades?tab=history"
         class="{tab_hist_cls}"
         style="padding:.5rem 1.2rem;text-decoration:none;font-weight:600;
                border-bottom:{'3px solid #2962ff' if tab=='history' else '3px solid transparent'};
                color:{'#fff' if tab=='history' else '#9ba3af'};">
        История <span style="background:#2a2e39;color:#9ba3af;border-radius:9px;
                              padding:1px 8px;font-size:.75rem;margin-left:4px;">{closed_cnt}</span>
      </a>
    </div>
    {tab_content}
    """
    return layout("Сделки", "Trades", body)


@app.get("/history", response_class=HTMLResponse)
def history() -> HTMLResponse:
    return RedirectResponse("/trades?tab=history", status_code=302)


@app.get("/trades/{signal_id}", response_class=HTMLResponse)
def trade_detail_page(signal_id: str) -> HTMLResponse:
    signal, outcome, notes = signal_detail(signal_id)
    if signal is None:
        body = f"""
        <div class="topbar"><div><h2>Сделка не найдена</h2><div class="muted">{html_escape(signal_id)}</div></div></div>
        <div class="band">Для этого ID нет события сигнала.</div>
        """
        return layout("Детали сделки", "Trades", body)

    side = signal.get("side", "")
    status = "closed" if outcome else "open"
    ret_text = "-"
    if outcome:
        entry = float(signal.get("entry_px") or 0.0)
        exit_px = float(outcome.get("exit_px") or 0.0)
        direction = 1 if side == "long" else -1
        ret_text = pct(direction * (exit_px - entry) / entry) if entry else "-"
    status_ru = "закрыта" if outcome else "открыта"
    metric_html = "".join([
        f'<div class="metric"><div class="label">Тикер</div><div class="value">{html_escape(signal.get("ticker", ""))}</div></div>',
        f'<div class="metric"><div class="label">Статус</div><div class="value">{pill(status_ru, status)}</div></div>',
        f'<div class="metric"><div class="label">Сторона</div><div class="value">{decision_pill(side)}</div></div>',
        f'<div class="metric"><div class="label">Доходность</div><div class="value">{ret_text}</div></div>',
    ])
    signal_rows = [
        ["Signal ID", f'<span class="code">{html_escape(signal_id)}</span>'],
        ["Таймфрейм", html_escape(signal.get("interval", ""))],
        ["Паттерн", html_escape(signal.get("fig_type", ""))],
        ["Время входа", dt_text(signal.get("entry_ts"))],
        ["Вход", price(signal.get("entry_px"))],
        ["Стоп (SL)", price(signal.get("stop_px"))],
        ["Цель (TP)", price(signal.get("target_px"))],
        ["R:R", rr_text(signal.get("entry_px"), signal.get("stop_px"), signal.get("target_px"))],
        ["Вероятность", probability_label(signal.get("probability"))],
        ["HTF контекст", html_escape(signal.get("htf_context", ""))],
        ["Источник", html_escape(signal.get("source", ""))],
    ]
    if outcome:
        signal_rows.extend([
            ["Время выхода", dt_text(outcome.get("exit_ts"))],
            ["Цена выхода", price(outcome.get("exit_px"))],
            ["Причина выхода", html_escape(outcome.get("exit_reason", ""))],
        ])
    note_rows = [
        [
            html_escape(row.get("recorded_at", "")),
            pill(row.get("tag", "note")),
            html_escape(row.get("author", "")),
            html_escape(row.get("note", "")),
        ]
        for row in reversed(notes)
    ]
    settle_form = "" if outcome else f"""
    <h3>Закрыть сделку</h3>
    <form class="band form-grid" method="post" action="/trades/settle">
      <input type="hidden" name="signal_id" value="{html_escape(signal_id)}">
      <label>Время выхода<input name="exit_ts" placeholder="2026-06-07T16:00:00Z" required></label>
      <label>Цена выхода<input name="exit_px" required></label>
      <label>Причина<select name="exit_reason"><option>tp</option><option>sl</option><option>time</option><option>manual</option><option>cancelled</option></select></label>
      <button class="btn" type="submit">Закрыть</button>
    </form>
    """
    body = f"""
    <div class="topbar"><div><h2>Детали сделки</h2><div class="muted">{html_escape(signal_id)}</div></div></div>
    <div class="grid">{metric_html}</div>
    <h3>Торговый чек-лист</h3>
    {table(["Проверка", "Значение"], checklist_rows(signal, outcome))}
    <h3>План риска</h3>
    {table(["Метрика", "Значение"], risk_plan_rows(signal))}
    <h3>Контракт сигнала</h3>
    {table(["Поле", "Значение"], signal_rows)}
    {settle_form}
    <h3>Заметки Антона</h3>
    {table(["Записано", "Тег", "Автор", "Заметка"], note_rows)}
    <form class="band form-grid" method="post" action="/trades/{html_escape(signal_id)}/notes">
      <label>Тег<select name="tag">
        <option>note</option>
        <option>late_entry</option>
        <option>ignored_htf</option>
        <option>moved_stop</option>
        <option>manual_exit</option>
        <option>news_risk</option>
        <option>good_execution</option>
      </select></label>
      <label>Автор<input name="author" value="anton"></label>
      <label>Заметка<input name="note" placeholder="Что произошло и почему" required></label>
      <button class="btn" type="submit">Добавить заметку</button>
    </form>
    """
    return layout("Детали сделки", "Trades", body)


@app.get("/backtest", response_class=HTMLResponse)
def backtest() -> HTMLResponse:
    return RedirectResponse("/settings#backtest", status_code=302)


@app.get("/settings", response_class=HTMLResponse)
def settings(tab: str = "stocks") -> HTMLResponse:
    watchlist    = read_watchlist()
    risk_settings = read_risk_settings()
    stocks       = wl_stocks(watchlist)
    crypto       = wl_crypto(watchlist)
    intervals    = wl_intervals(watchlist)

    # Backtest section
    data       = dashboard_payload()
    historical = data["backtest"].get("portfolio", {})
    forward    = data["forward_summary"]
    bt_rows    = [
        ["Бэктест (база)", historical.get("trades", 0), pct(historical.get("winrate")), pct(historical.get("expectancy")), fmt(historical.get("profit_factor")), pct(historical.get("max_drawdown"))],
        ["Forward (закрытые)", forward.get("trades", 0),    pct(forward.get("winrate")),    pct(forward.get("expectancy")),    fmt(forward.get("profit_factor")),    pct(forward.get("max_drawdown"))],
    ]

    # Ticker chips helper
    def ticker_chips(tickers: list[str], group: str) -> str:
        chips = "".join(
            f'<span style="display:inline-flex;align-items:center;gap:4px;background:#1e222d;color:#c9d1d9;'
            f'border:1px solid #2a2e39;border-radius:6px;padding:3px 8px;font-size:.8rem;margin:2px;">'
            f'{html_escape(t)}'
            f'<form class="inline" method="post" action="/settings/watchlist/remove-ticker" style="margin:0">'
            f'<input type="hidden" name="ticker" value="{html_escape(t)}">'
            f'<input type="hidden" name="group" value="{group}">'
            f'<button type="submit" style="background:none;border:none;color:#9ba3af;cursor:pointer;'
            f'padding:0 2px;font-size:.9rem;line-height:1">×</button>'
            f'</form></span>'
            for t in tickers
        )
        return f'<div style="display:flex;flex-wrap:wrap;gap:2px;padding:.75rem;">{chips}</div>' if chips else \
               '<div class="muted" style="padding:.75rem;">Нет тикеров</div>'

    # Interval checkboxes
    all_tfs = ["1d", "4h", "1h", "1w"]
    tf_boxes = "".join(
        f'<label style="display:inline-flex;align-items:center;gap:6px;margin-right:16px;cursor:pointer;">'
        f'<input type="checkbox" name="intervals" value="{tf}" {"checked" if tf in intervals else ""}> {tf}</label>'
        for tf in all_tfs
    )

    stocks_tab_style = "border-bottom:3px solid #2962ff;color:#fff;" if tab == "stocks" else "border-bottom:3px solid transparent;color:#9ba3af;"
    crypto_tab_style = "border-bottom:3px solid #2962ff;color:#fff;" if tab == "crypto" else "border-bottom:3px solid transparent;color:#9ba3af;"

    if tab == "crypto":
        active_chips  = ticker_chips(crypto, "crypto")
        add_placeholder = "BTC-USD"
        add_group = "crypto"
        active_count = len(crypto)
    else:
        active_chips  = ticker_chips(stocks, "stocks")
        add_placeholder = "AAPL"
        add_group = "stocks"
        active_count = len(stocks)

    body = f"""
    <div class="topbar"><div><h2>Settings</h2>
      <div class="muted">Тикеры для мониторинга и риск-параметры.</div>
    </div></div>

    <h3 id="backtest">Бэктест против Forward</h3>
    {table(["Период", "Сделок", "Винрейт", "Ожидание", "PF", "Просадка"], bt_rows)}
    <div class="band" style="margin-top:0">Правило: меньше 30 закрытых forward-сделок — только наблюдение. PF &lt; 1.1 или отрицательная expectancy — автоматизацию не включать.</div>

    <h3>Вотчлист</h3>
    <div style="display:flex;gap:.5rem;margin:0 1.5rem .5rem;border-bottom:1px solid #2a2e39;">
      <a href="/settings?tab=stocks" style="padding:.5rem 1.2rem;text-decoration:none;font-weight:600;{stocks_tab_style}">
        Акции <span style="background:#2a2e39;color:#9ba3af;border-radius:9px;padding:1px 8px;font-size:.75rem;margin-left:4px;">{len(stocks)}</span>
      </a>
      <a href="/settings?tab=crypto" style="padding:.5rem 1.2rem;text-decoration:none;font-weight:600;{crypto_tab_style}">
        Крипто <span style="background:#2a2e39;color:#9ba3af;border-radius:9px;padding:1px 8px;font-size:.75rem;margin-left:4px;">{len(crypto)}</span>
      </a>
    </div>
    <div class="band" style="margin-top:0;padding:.5rem 0;">
      {active_chips}
      <form class="inline" method="post" action="/settings/watchlist/add-ticker"
            style="display:flex;gap:.5rem;padding:.5rem .75rem 0;">
        <input type="hidden" name="group" value="{add_group}">
        <input name="ticker" placeholder="{add_placeholder}" style="width:120px;" required>
        <button class="btn mini" type="submit">+ Добавить</button>
      </form>
    </div>

    <h3>Таймфреймы для сканирования</h3>
    <form class="band" method="post" action="/settings/watchlist/save-intervals">
      {tf_boxes}
      <button class="btn mini" type="submit" style="margin-left:8px;">Сохранить</button>
    </form>

    <form class="band" method="post" action="/settings/run-scan" style="margin-top:.5rem">
      <button class="btn" type="submit">▶ Запустить скан</button>
      <span class="muted">Обновляет Signals и Action Board по всем таймфреймам.</span>
    </form>

    <h3>Risk Settings</h3>
    <form class="band form-grid" method="post" action="/settings/risk/save">
      <label>Размер счёта ($)<input name="account_size" value="{html_escape(risk_settings.get("account_size", 10000))}"></label>
      <label>Риск на сделку %<input name="risk_pct" value="{html_escape(risk_settings.get("risk_pct", 1.0))}"></label>
      <label>Макс. позиция %<input name="max_position_pct" value="{html_escape(risk_settings.get("max_position_pct", 25.0))}"></label>
      <label>Валюта<input name="currency" value="{html_escape(risk_settings.get("currency", "USD"))}"></label>
      <button class="btn" type="submit">Сохранить риск</button>
    </form>
    """
    return layout("Настройки", "Settings", body)


@app.post("/trades/settle")
async def settle_trade(request: Request) -> RedirectResponse:
    body = (await request.body()).decode("utf-8")
    form = {key: values[0] for key, values in parse_qs(body).items()}
    append_jsonl(FORWARD_LOG, outcome_event(
        signal_id=form["signal_id"],
        exit_ts=form["exit_ts"],
        exit_px=float(form["exit_px"]),
        exit_reason=form.get("exit_reason", "manual"),
    ))
    return RedirectResponse(f"/trades/{form['signal_id']}", status_code=303)


@app.post("/trades/{signal_id}/notes")
async def add_trade_note(signal_id: str, request: Request) -> RedirectResponse:
    body = (await request.body()).decode("utf-8")
    form = {key: values[0] for key, values in parse_qs(body).items()}
    append_jsonl(FORWARD_LOG, note_event(
        signal_id=signal_id,
        note=form["note"],
        tag=form.get("tag", "note"),
        author=form.get("author", "anton"),
    ))
    return RedirectResponse(f"/trades/{signal_id}", status_code=303)


@app.post("/alerts/add")
async def add_alert(request: Request) -> RedirectResponse:
    body = (await request.body()).decode("utf-8")
    form = {key: values[0] for key, values in parse_qs(body).items()}
    append_jsonl(FORWARD_LOG, signal_event(
        ticker=form["ticker"],
        interval=form["interval"],
        action=form["action"],
        entry_ts=form["entry_ts"],
        entry_px=float(form["entry_px"]),
        stop_px=float(form["stop_px"]) if form.get("stop_px") else None,
        target_px=float(form["target_px"]) if form.get("target_px") else None,
        fig_type=form.get("fig_type") or "unknown",
        probability=float(form["probability"]) if form.get("probability") else None,
        htf_context=form.get("htf_context", ""),
        source="dashboard_manual",
    ))
    return RedirectResponse("/signals", status_code=303)


@app.post("/signals/accept")
async def accept_signal(request: Request) -> RedirectResponse:
    body = (await request.body()).decode("utf-8")
    form = {key: values[0] for key, values in parse_qs(body).items()}
    row = signal_event(
        ticker=form["ticker"],
        interval=form["interval"],
        action=form["action"],
        entry_ts=form["entry_ts"],
        entry_px=float(form["entry_px"]),
        stop_px=float(form["stop_px"]) if form.get("stop_px") else None,
        target_px=float(form["target_px"]) if form.get("target_px") else None,
        fig_type=form.get("fig_type") or "unknown",
        probability=float(form["probability"]) if form.get("probability") else None,
        htf_context=form.get("htf_context", ""),
        source="dashboard_scanner_accept",
    )
    append_jsonl(FORWARD_LOG, row)
    return RedirectResponse(f"/trades/{row['signal_id']}", status_code=303)


@app.post("/settings/watchlist/add-ticker")
async def watchlist_add_ticker(request: Request) -> RedirectResponse:
    body = (await request.body()).decode("utf-8")
    form = {key: values[0] for key, values in parse_qs(body).items()}
    ticker = form.get("ticker", "").strip().upper()
    group  = form.get("group", "stocks")  # "stocks" or "crypto"
    if ticker:
        wl = read_watchlist()
        lst = wl.setdefault(group, [])
        if ticker not in [str(t).upper() for t in lst]:
            lst.append(ticker)
        write_watchlist(wl)
    return RedirectResponse(f"/settings?tab={group}", status_code=303)


@app.post("/settings/watchlist/remove-ticker")
async def watchlist_remove_ticker(request: Request) -> RedirectResponse:
    body = (await request.body()).decode("utf-8")
    form = {key: values[0] for key, values in parse_qs(body).items()}
    ticker = form.get("ticker", "").strip().upper()
    group  = form.get("group", "stocks")
    if ticker:
        wl = read_watchlist()
        wl[group] = [t for t in wl.get(group, []) if str(t).upper() != ticker]
        write_watchlist(wl)
    return RedirectResponse(f"/settings?tab={group}", status_code=303)


@app.post("/settings/watchlist/save-intervals")
async def watchlist_save_intervals(request: Request) -> RedirectResponse:
    body = (await request.body()).decode("utf-8")
    form = parse_qs(body)
    intervals = form.get("intervals", ["1d"])
    wl = read_watchlist()
    wl["intervals"] = intervals
    write_watchlist(wl)
    return RedirectResponse("/settings", status_code=303)


@app.post("/settings/risk/save")
async def save_risk_settings(request: Request) -> RedirectResponse:
    body = (await request.body()).decode("utf-8")
    form = {key: values[0] for key, values in parse_qs(body).items()}
    write_risk_settings(clean_risk_form(form))
    return RedirectResponse("/settings", status_code=303)


@app.post("/settings/run-scan")
def run_scan() -> RedirectResponse:
    subprocess.run([sys.executable, "python/scripts/daily_report.py"], cwd=REPO, check=False)
    return RedirectResponse("/action-board", status_code=303)


@app.post("/actions/run-strategy")
def run_strategy() -> RedirectResponse:
    subprocess.run([str(REPO / "scripts" / "run_strategy_system.sh")], cwd=REPO, check=False)
    return RedirectResponse("/", status_code=303)


@app.post("/api/alerts/tradingview")
async def api_tradingview_alert(request: Request) -> JSONResponse:
    payload = await request.json()
    row = signal_event_from_payload(payload, source="tradingview_webhook")
    append_jsonl(FORWARD_LOG, row)
    return JSONResponse({
        "ok": True,
        "signal_id": row["signal_id"],
        "ticker": row["ticker"],
        "interval": row["interval"],
        "side": row["side"],
    })


# ─────────── AUTO-TRADER ───────────

def auto_trader_running() -> bool:
    """The trader runs hourly via launchd (StartCalendarInterval :01), so it is
    NOT a persistent process — a pid check would read STOPPED between passes.
    Treat it as active if the last scan landed within the last 90 min (hourly
    cadence + one cycle of grace). A live manual run also refreshes last_scan,
    so this covers both modes."""
    state = auto_trader_state()
    ts = state.get("last_scan")
    if not ts:
        # fall back to the pid for a freshly-started manual run with no scan yet
        if not AUTO_TRADER_PID.exists():
            return False
        try:
            import os
            os.kill(int(AUTO_TRADER_PID.read_text().strip()), 0)
            return True
        except Exception:
            return False
    try:
        last = pd.Timestamp(ts)
        if last.tzinfo is None:
            last = last.tz_localize("UTC")
        age_s = (pd.Timestamp.now("UTC") - last).total_seconds()
        return age_s < 90 * 60
    except Exception:
        return False


def auto_trader_state() -> dict:
    if not AUTO_TRADER_STATE.exists():
        return {}
    try:
        return json.loads(AUTO_TRADER_STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def auto_trader_last_log(n: int = 8) -> list[str]:
    if not AUTO_TRADER_LOG.exists():
        return []
    lines = AUTO_TRADER_LOG.read_text(encoding="utf-8").splitlines()
    return lines[-n:]


def auto_trader_widget() -> str:
    running = auto_trader_running()
    state   = auto_trader_state()
    status_pill = '<span class="pill buy">RUNNING</span>' if running else '<span class="pill observe">STOPPED</span>'
    last_scan   = html_escape(state.get("last_scan", "—"))
    last_retrain= html_escape(state.get("last_retrain", "—"))
    pending     = state.get("closed_since_retrain", 0)
    log_lines   = auto_trader_last_log()
    log_html    = "\n".join(html_escape(l) for l in log_lines) or "нет логов"

    start_btn = "" if running else """
      <form class="inline" method="post" action="/auto-trader/start">
        <button class="btn" type="submit">▶ Запустить</button>
      </form>"""
    stop_btn = "" if not running else """
      <form class="inline" method="post" action="/auto-trader/stop">
        <button class="btn secondary" type="submit">■ Остановить</button>
      </form>"""
    run_once_btn = """
      <form class="inline" method="post" action="/auto-trader/run-once">
        <button class="btn secondary" type="submit">↻ Один проход</button>
      </form>"""

    return f"""
    <div class="band">
      <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap;margin-bottom:12px">
        {status_pill}
        {start_btn}{stop_btn}{run_once_btn}
        <span class="muted" style="font-size:13px">Последний скан: {last_scan}</span>
        <span class="muted" style="font-size:13px">Последний ретрейн: {last_retrain}</span>
        <span class="muted" style="font-size:13px">До ретрейна: {pending}/{RETRAIN_EVERY}</span>
      </div>
      <pre style="background:#f0f4f8;border-radius:6px;padding:10px;font-size:12px;margin:0;overflow-x:auto;max-height:160px;overflow-y:auto">{log_html}</pre>
    </div>"""


# ─────────── PORTFOLIO ───────────

def read_portfolio() -> list[dict]:
    if not PORTFOLIO_FILE.exists():
        return []
    try:
        return json.loads(PORTFOLIO_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def write_portfolio(holdings: list[dict]) -> None:
    PORTFOLIO_FILE.parent.mkdir(parents=True, exist_ok=True)
    PORTFOLIO_FILE.write_text(json.dumps(holdings, indent=2, ensure_ascii=False), encoding="utf-8")


def fetch_prices(tickers: list[str], timeout: float = 8.0) -> dict[str, float | None]:
    if not tickers:
        return {}
    import concurrent.futures

    def _get_price(sym: str) -> tuple[str, float | None]:
        # Provider first (Binance/Tiingo), yfinance fallback.
        try:
            from ewb.research.providers import last_price
            px = last_price(sym)
            if px:
                return sym.upper(), float(px)
        except Exception:
            pass
        try:
            import yfinance as yf
            return sym.upper(), yf.Ticker(sym).fast_info.last_price
        except Exception:
            return sym.upper(), None

    result: dict[str, float | None] = {}
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(tickers), 8)) as ex:
            futs = {ex.submit(_get_price, t): t for t in tickers}
            done, _ = concurrent.futures.wait(futs, timeout=timeout)
            for f in done:
                sym, px = f.result()
                result[sym] = px
            for f in futs:
                if f not in done:
                    result[futs[f].upper()] = None
        return result
    except Exception:
        return {t.upper(): None for t in tickers}


def portfolio_rows(holdings: list[dict], prices: dict[str, float | None]) -> list[list]:
    rows = []
    for h in holdings:
        hid = html_escape(h.get("id", ""))
        ticker = h.get("ticker", "").upper()
        qty = h.get("qty", 0)
        avg = h.get("avg_price", 0.0)
        notes = h.get("notes", "")
        added = h.get("added_at", "")[:10]
        cur_px = prices.get(ticker)
        cost = qty * avg
        cur_val = qty * cur_px if cur_px is not None else None
        pnl = cur_val - cost if cur_val is not None else None
        pnl_pct = pnl / cost * 100 if cost > 0 and pnl is not None else None

        cur_px_str = f"${cur_px:,.2f}" if cur_px is not None else '<span class="muted">—</span>'
        cur_val_str = f"${cur_val:,.2f}" if cur_val is not None else '<span class="muted">—</span>'
        if pnl is not None and pnl_pct is not None:
            sign = "+" if pnl >= 0 else ""
            css = "buy" if pnl >= 0 else "sell"
            pnl_str = f'<span class="pill {css}">{sign}${pnl:,.2f} ({sign}{pnl_pct:.1f}%)</span>'
        else:
            pnl_str = '<span class="muted">—</span>'

        edit_form = f"""
        <form class="inline" method="post" action="/portfolio/edit">
          <input type="hidden" name="id" value="{hid}">
          <button class="btn secondary mini" type="button"
            onclick="openEdit('{hid}','{html_escape(ticker)}','{qty}','{avg}','{html_escape(notes)}')">Edit</button>
        </form>
        <form class="inline" method="post" action="/portfolio/delete"
          onsubmit="return confirm('Удалить {html_escape(ticker)}?')">
          <input type="hidden" name="id" value="{hid}">
          <button class="btn mini" style="border-color:#b42318;background:#b42318" type="submit">Del</button>
        </form>"""

        rows.append([
            f"<strong>{html_escape(ticker)}</strong>",
            f"{qty:g}",
            f"${avg:,.2f}",
            f"${cost:,.2f}",
            cur_px_str,
            cur_val_str,
            pnl_str,
            html_escape(notes),
            html_escape(added),
            edit_form,
        ])
    return rows


def portfolio_totals(holdings: list[dict], prices: dict[str, float | None]) -> tuple[float, float | None]:
    total_cost = sum(h.get("qty", 0) * h.get("avg_price", 0.0) for h in holdings)
    total_val = None
    val_acc = 0.0
    all_known = True
    for h in holdings:
        px = prices.get(h.get("ticker", "").upper())
        if px is None:
            all_known = False
            break
        val_acc += h.get("qty", 0) * px
    if all_known and holdings:
        total_val = val_acc
    return total_cost, total_val


@app.get("/portfolio", response_class=HTMLResponse)
def portfolio_page() -> HTMLResponse:
    holdings = read_portfolio()
    tickers = list({h.get("ticker", "").upper() for h in holdings if h.get("ticker")})
    prices = fetch_prices(tickers)
    rows = portfolio_rows(holdings, prices)
    total_cost, total_val = portfolio_totals(holdings, prices)

    cost_str = f"${total_cost:,.2f}"
    val_str = f"${total_val:,.2f}" if total_val is not None else "—"
    if total_val is not None and total_cost > 0:
        pnl = total_val - total_cost
        pnl_pct = pnl / total_cost * 100
        sign = "+" if pnl >= 0 else ""
        css = "buy" if pnl >= 0 else "sell"
        total_pnl_str = f'<span class="pill {css}">{sign}${pnl:,.2f} ({sign}{pnl_pct:.1f}%)</span>'
    else:
        total_pnl_str = "—"

    metrics = f"""
    <div class="grid" style="grid-template-columns:repeat(3,minmax(0,1fr))">
      <div class="metric"><div class="label">Позиций</div><div class="value">{len(holdings)}</div></div>
      <div class="metric"><div class="label">Вложено</div><div class="value">{cost_str}</div></div>
      <div class="metric"><div class="label">Текущая стоимость / P&L</div><div class="value" style="font-size:18px">{val_str} &nbsp;{total_pnl_str}</div></div>
    </div>"""

    tbl = table(
        ["Тикер", "Кол-во", "Ср. цена", "Вложено", "Тек. цена", "Тек. стоимость", "P&L", "Заметки", "Добавлено", ""],
        rows,
    )

    body = f"""
    <div class="topbar">
      <div><h2>Портфель</h2><div class="muted">Ручной учёт позиций. Текущие цены — Yahoo Finance.</div></div>
      <form method="get" action="/portfolio"><button class="btn secondary" type="submit">↻ Обновить цены</button></form>
    </div>
    {metrics}
    <h3>Добавить позицию</h3>
    <form class="band form-grid" method="post" action="/portfolio/add">
      <label>Тикер<input name="ticker" placeholder="AAPL" required style="text-transform:uppercase"></label>
      <label>Количество<input name="qty" type="number" step="any" min="0.000001" placeholder="10" required></label>
      <label>Средняя цена ($)<input name="avg_price" type="number" step="any" min="0" placeholder="180.50" required></label>
      <label>Заметки<input name="notes" placeholder="необязательно"></label>
      <button class="btn" type="submit" style="align-self:end">Добавить</button>
    </form>
    <h3>Мои позиции</h3>
    {tbl}

    <!-- Edit modal -->
    <div id="edit-modal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:999;align-items:center;justify-content:center">
      <div style="background:#fff;border-radius:10px;padding:28px 32px;width:420px;max-width:95vw">
        <h3 style="margin-top:0">Редактировать позицию</h3>
        <form method="post" action="/portfolio/edit">
          <input type="hidden" id="edit-id" name="id">
          <label style="display:block;margin-bottom:10px">Тикер
            <input id="edit-ticker" name="ticker" required style="width:100%;margin-top:4px;border:1px solid #d9dee7;border-radius:6px;padding:9px 10px;font:inherit">
          </label>
          <label style="display:block;margin-bottom:10px">Количество
            <input id="edit-qty" name="qty" type="number" step="any" min="0.000001" required style="width:100%;margin-top:4px;border:1px solid #d9dee7;border-radius:6px;padding:9px 10px;font:inherit">
          </label>
          <label style="display:block;margin-bottom:10px">Средняя цена ($)
            <input id="edit-avg" name="avg_price" type="number" step="any" min="0" required style="width:100%;margin-top:4px;border:1px solid #d9dee7;border-radius:6px;padding:9px 10px;font:inherit">
          </label>
          <label style="display:block;margin-bottom:16px">Заметки
            <input id="edit-notes" name="notes" style="width:100%;margin-top:4px;border:1px solid #d9dee7;border-radius:6px;padding:9px 10px;font:inherit">
          </label>
          <div style="display:flex;gap:10px">
            <button class="btn" type="submit">Сохранить</button>
            <button class="btn secondary" type="button" onclick="closeEdit()">Отмена</button>
          </div>
        </form>
      </div>
    </div>
    <script>
      function openEdit(id, ticker, qty, avg, notes) {{
        document.getElementById('edit-id').value = id;
        document.getElementById('edit-ticker').value = ticker;
        document.getElementById('edit-qty').value = qty;
        document.getElementById('edit-avg').value = avg;
        document.getElementById('edit-notes').value = notes;
        var m = document.getElementById('edit-modal');
        m.style.display = 'flex';
      }}
      function closeEdit() {{
        document.getElementById('edit-modal').style.display = 'none';
      }}
      document.getElementById('edit-modal').addEventListener('click', function(e) {{
        if (e.target === this) closeEdit();
      }});
    </script>
    """
    return layout("Портфель", "Portfolio", body)


@app.post("/portfolio/add")
async def portfolio_add(request: Request) -> RedirectResponse:
    form = dict(await request.form())
    ticker = str(form.get("ticker", "")).strip().upper()
    if not ticker:
        return RedirectResponse("/portfolio", status_code=303)
    try:
        qty = float(form.get("qty", 0))
        avg_price = float(form.get("avg_price", 0))
    except (ValueError, TypeError):
        return RedirectResponse("/portfolio", status_code=303)
    holdings = read_portfolio()
    holdings.append({
        "id": str(uuid.uuid4()),
        "ticker": ticker,
        "qty": qty,
        "avg_price": avg_price,
        "notes": str(form.get("notes", "")).strip(),
        "added_at": datetime.now(timezone.utc).isoformat(),
    })
    write_portfolio(holdings)
    return RedirectResponse("/portfolio", status_code=303)


@app.post("/portfolio/edit")
async def portfolio_edit(request: Request) -> RedirectResponse:
    form = dict(await request.form())
    hid = str(form.get("id", "")).strip()
    holdings = read_portfolio()
    for h in holdings:
        if h.get("id") == hid:
            ticker = str(form.get("ticker", h["ticker"])).strip().upper()
            if ticker:
                h["ticker"] = ticker
            try:
                h["qty"] = float(form.get("qty", h["qty"]))
                h["avg_price"] = float(form.get("avg_price", h["avg_price"]))
            except (ValueError, TypeError):
                pass
            h["notes"] = str(form.get("notes", h.get("notes", ""))).strip()
            break
    write_portfolio(holdings)
    return RedirectResponse("/portfolio", status_code=303)


@app.post("/portfolio/delete")
async def portfolio_delete(request: Request) -> RedirectResponse:
    form = dict(await request.form())
    hid = str(form.get("id", "")).strip()
    holdings = [h for h in read_portfolio() if h.get("id") != hid]
    write_portfolio(holdings)
    return RedirectResponse("/portfolio", status_code=303)


@app.post("/auto-trader/start")
def auto_trader_start() -> RedirectResponse:
    if not auto_trader_running():
        log_fh = open(AUTO_TRADER_LOG, "a")
        # --once: a single manual scan, consistent with the hourly launchd cron
        # (EPIC L). It takes the same single-instance lock, so a manual "scan now"
        # never races a cron pass that is still running.
        proc = subprocess.Popen(
            [sys.executable, "-m", "ewb.auto_trader", "--once"],
            cwd=REPO / "python",
            stdout=log_fh,
            stderr=log_fh,
            start_new_session=True,
        )
        AUTO_TRADER_PID.write_text(str(proc.pid))
    return RedirectResponse("/", status_code=303)


@app.post("/auto-trader/stop")
def auto_trader_stop() -> RedirectResponse:
    if AUTO_TRADER_PID.exists():
        try:
            import os, signal as _sig
            pid = int(AUTO_TRADER_PID.read_text().strip())
            os.kill(pid, _sig.SIGTERM)
        except Exception:
            pass
        AUTO_TRADER_PID.unlink(missing_ok=True)
    return RedirectResponse("/", status_code=303)


@app.post("/auto-trader/run-once")
def auto_trader_run_once() -> RedirectResponse:
    log_fh = open(AUTO_TRADER_LOG, "a")
    subprocess.Popen(
        [sys.executable, "-m", "ewb.auto_trader", "--once"],
        cwd=REPO / "python",
        stdout=log_fh,
        stderr=log_fh,
    )
    return RedirectResponse("/", status_code=303)


@app.get("/api/portfolio")
def api_portfolio() -> JSONResponse:
    holdings = read_portfolio()
    tickers = list({h.get("ticker", "").upper() for h in holdings if h.get("ticker")})
    prices = fetch_prices(tickers)
    result = []
    for h in holdings:
        px = prices.get(h.get("ticker", "").upper())
        cost = h["qty"] * h["avg_price"]
        cur_val = h["qty"] * px if px is not None else None
        result.append({**h, "current_price": px, "current_value": cur_val,
                        "pnl": (cur_val - cost) if cur_val is not None else None})
    return JSONResponse(result)


@app.get("/api/status")
def api_status() -> dict[str, Any]:
    data = dashboard_payload()
    return {
        "decision": data["daily"].get("decision", "OBSERVE"),
        "open": int(len(data["open"])),
        "closed": int(len(data["closed"])),
        "baseline_trades": data["backtest"].get("portfolio", {}).get("trades", 0),
    }
