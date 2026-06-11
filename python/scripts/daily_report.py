"""Generate Anton's daily probability signal report from a watchlist config."""
from __future__ import annotations

import argparse
import json
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ewb.research import load_probability_calibration, log_processing_error
from scripts.scan_probability_signals import (
    DEFAULT_CALIBRATION,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_PERIODS,
    build_payload,
    filter_fresh_signals,
    fmt_px,
    money_pct,
    parse_signal_ts,
    pct,
    scan_ticker,
)


REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_CONFIG = os.path.join(REPO, "configs", "watchlist.yaml")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", default=DEFAULT_CONFIG, help="Watchlist YAML path")
    p.add_argument("--calibration", default=DEFAULT_CALIBRATION, help="Calibration JSON path")
    p.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Output directory")
    return p


def load_watchlist(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    # Support new format (stocks/crypto/intervals) and legacy format (tickers/interval)
    if "stocks" in data or "crypto" in data:
        raw = list(data.get("stocks", [])) + list(data.get("crypto", []))
    else:
        raw = data.get("tickers", [])
    tickers = [str(t).strip().upper() for t in raw if str(t).strip()]
    if not tickers:
        raise ValueError("watchlist config must contain at least one ticker")

    # Support new intervals list and legacy single interval
    if "intervals" in data:
        intervals = [str(i) for i in data["intervals"]]
    else:
        intervals = [str(data.get("interval", "1d"))]

    actions = [str(a).strip() for a in data.get("actions", ["buy", "sell"]) if str(a).strip()]
    return {
        "tickers": tickers,
        "intervals": intervals,
        "interval": intervals[0],   # kept for backward-compat with callers
        "period": data.get("period"),
        "actions": actions,
        "fresh_hours": data.get("fresh_hours"),
        "fresh_days": data.get("fresh_days"),
        "limit": int(data.get("limit", 200)),
    }


def russian_action(action: str) -> str:
    return {
        "buy": "ПОКУПАТЬ",
        "sell": "ПРОДАВАТЬ",
        "wait": "ЖДАТЬ",
        "skip": "ПРОПУСТИТЬ",
    }.get(action, action)


def signal_strength(signal: dict) -> str:
    action = signal.get("recommended_action")
    if action == "skip":
        return "Skip"
    if action == "wait":
        return "Wait"
    if action not in {"buy", "sell"}:
        return "n/a"

    p_trade_win = signal.get("p_trade_win")
    expected = signal.get("expected_net_return")
    confidence = signal.get("confidence")
    if p_trade_win is None or expected is None:
        return "C"
    if expected <= 0:
        return "C"
    if p_trade_win >= 0.55 and expected >= 0.003 and confidence in {"high", "very_high"}:
        return "A"
    if p_trade_win >= 0.52 and expected > 0:
        return "B"
    return "C"


def signal_sort_key(signal: dict) -> tuple:
    strength_rank = {
        "A": 0,
        "B": 1,
        "C": 2,
        "Wait": 3,
        "Skip": 4,
        "n/a": 5,
    }
    expected = signal.get("expected_net_return")
    if expected is None:
        expected = -999.0
    entry_ts = parse_signal_ts(signal.get("entry_ts"))
    entry_sort = -(entry_ts.timestamp()) if entry_ts is not None else 0.0
    return (
        strength_rank.get(signal_strength(signal), 5),
        -float(expected),
        entry_sort,
    )


def sort_daily_signals(signals: list[dict]) -> list[dict]:
    return sorted(signals, key=signal_sort_key)


def risk_metrics(signal: dict) -> dict:
    risk = signal.get("risk_box", {})
    entry = risk.get("entry_px")
    stop = risk.get("stop_px")
    target = risk.get("target_px")
    if entry is None or stop is None or target is None:
        return {"risk_per_share": None, "reward_per_share": None, "rr": None}
    risk_per_share = abs(float(entry) - float(stop))
    reward_per_share = abs(float(target) - float(entry))
    rr = reward_per_share / risk_per_share if risk_per_share > 0 else None
    return {
        "risk_per_share": risk_per_share,
        "reward_per_share": reward_per_share,
        "rr": rr,
    }


def fmt_rr(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}"


def decision_reason(signal: dict) -> str:
    action = signal.get("recommended_action")
    pattern = signal.get("pattern", "n/a")
    p_trade_win = signal.get("p_trade_win")
    expected = signal.get("expected_net_return")
    confidence = signal.get("confidence", "unknown")
    if action in {"buy", "sell"}:
        return (
            f"{pattern}: исторически даёт торговый edge "
            f"({pct(p_trade_win)}, EV {money_pct(expected)}, confidence {confidence})."
        )
    if action == "skip":
        if pattern in {"impulse", "triangle"}:
            return (
                f"{pattern}: в модели v0 это no-trade паттерн; "
                f"используется как контекст, а не как самостоятельный вход "
                f"({pct(p_trade_win)}, EV {money_pct(expected)})."
            )
        return (
            f"{pattern}: вход пропущен, потому что исторический EV не подтверждает сделку "
            f"({pct(p_trade_win)}, EV {money_pct(expected)})."
        )
    if action == "wait":
        return f"{pattern}: недостаточно подтверждения для сделки, лучше ждать."
    return f"{pattern}: нет достаточных данных для торгового решения."


def russian_daily_report(payload: dict) -> str:
    freshness = payload.get("freshness") or "all"
    no_signal_tickers = payload.get("no_signal_tickers", [])
    last_signal_by_ticker = payload.get("last_signal_by_ticker", {})
    lines = [
        "# Ежедневный отчёт сигналов",
        "",
        f"Сформировано: `{payload['generated_at']}`",
        f"Модель: `{payload['model_version']}`",
        f"Watchlist: `{', '.join(payload['tickers'])}`",
        f"Таймфрейм: `{payload['interval']}`",
        f"Свежесть: `{freshness}`",
        f"Сигналов: `{payload['n_signals']}`",
        "",
    ]
    if not payload["signals"]:
        lines.extend([
            "Свежих торговых сигналов нет.",
            "",
            "Это нормальный результат: система не должна заставлять Антона входить без подтверждённого edge.",
        ])
        return "\n".join(lines) + "\n"

    lines.extend([
        "| Акция | Сила | Действие | Фигура | P(win) | EV | Вход | Стоп | Цель |",
        "|---|---|---|---|---:|---:|---:|---:|---:|",
    ])
    for signal in payload["signals"]:
        risk = signal.get("risk_box", {})
        lines.append(
            f"| {signal.get('ticker')} | {signal_strength(signal)} | "
            f"{russian_action(signal.get('recommended_action'))} | "
            f"{signal.get('pattern')} | "
            f"{pct(signal.get('p_trade_win'))} | {money_pct(signal.get('expected_net_return'))} | "
            f"{fmt_px(risk.get('entry_px'))} | "
            f"{fmt_px(risk.get('stop_px'))} | {fmt_px(risk.get('target_px'))} | "
        )

    lines.extend(["", "Детали свежих сигналов:", ""])
    for signal in payload["signals"]:
        metrics = risk_metrics(signal)
        lines.extend([
            f"**{signal.get('ticker')}**",
            f"- Время сигнала: `{signal.get('entry_ts')}`",
            f"- Уверенность: `{signal.get('confidence')}`",
            (
                f"- Риск/потенциал: риск на акцию `{fmt_px(metrics.get('risk_per_share'))}`, "
                f"потенциал `{fmt_px(metrics.get('reward_per_share'))}`, R:R `{fmt_rr(metrics.get('rr'))}`"
            ),
            f"- Причина: {decision_reason(signal)}",
            "",
        ])

    if no_signal_tickers:
        lines.extend([
            "Без свежего торгового сигнала:",
            "",
            "| Акция | Сила | Последнее наблюдение | Действие | Фигура | P(win) | EV |",
            "|---|---|---|---|---|---:|---:|",
        ])
        for ticker in no_signal_tickers:
            last_signal = last_signal_by_ticker.get(ticker) or {}
            lines.append(
                f"| {ticker} | {signal_strength(last_signal)} | "
                f"{last_signal.get('entry_ts', 'не найдено')} | "
                f"{russian_action(last_signal.get('recommended_action', 'n/a'))} | "
                f"{last_signal.get('pattern', 'n/a')} | "
                f"{pct(last_signal.get('p_trade_win'))} | "
                f"{money_pct(last_signal.get('expected_net_return'))} |"
            )
        lines.extend(["", "Причины пропуска:", ""])
        for ticker in no_signal_tickers:
            last_signal = last_signal_by_ticker.get(ticker) or {}
            lines.append(f"- **{ticker}**: {decision_reason(last_signal)}")
    return "\n".join(lines) + "\n"


def build_daily_payload(config: dict, calibration: dict) -> dict:
    intervals = config.get("intervals", [config.get("interval", "1d")])
    interval  = intervals[0]   # primary interval for backward-compat reporting
    actions   = set(config["actions"])
    all_signals: list[dict] = []
    for tf in intervals:
        period = config.get("period") or DEFAULT_PERIODS.get(tf, "730d")
        for ticker in config["tickers"]:
            try:
                all_signals.extend(scan_ticker(ticker, tf, period, calibration))
            except Exception as exc:
                log_processing_error(ticker, tf, exc, context="daily_report")
    filtered = [
        signal
        for signal in all_signals
        if signal["recommended_action"] in actions
    ]
    all_signals.sort(key=lambda signal: signal.get("entry_ts") or "", reverse=True)
    last_signal_by_ticker = {}
    for signal in all_signals:
        ticker = signal.get("ticker")
        if ticker and ticker not in last_signal_by_ticker:
            last_signal_by_ticker[ticker] = signal

    filtered = filter_fresh_signals(
        filtered,
        fresh_hours=config.get("fresh_hours"),
        fresh_days=config.get("fresh_days"),
    )
    filtered = sort_daily_signals(filtered)
    payload = build_payload(
        filtered[:config["limit"]],
        tickers=config["tickers"],
        interval=interval,
        period=period,
        actions=actions,
        limit=config["limit"],
        calibration=calibration,
        fresh_hours=config.get("fresh_hours"),
        fresh_days=config.get("fresh_days"),
    )
    signal_tickers = {signal.get("ticker") for signal in payload["signals"]}
    payload["no_signal_tickers"] = [
        ticker for ticker in config["tickers"] if ticker not in signal_tickers
    ]
    payload["last_signal_by_ticker"] = {
        ticker: last_signal_by_ticker[ticker]
        for ticker in payload["no_signal_tickers"]
        if ticker in last_signal_by_ticker
    }
    return payload


def save_daily_outputs(payload: dict, output_dir: str) -> tuple[str, str]:
    os.makedirs(output_dir, exist_ok=True)
    json_path = os.path.join(output_dir, "daily_report.json")
    md_path = os.path.join(output_dir, "daily_report.md")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(russian_daily_report(payload))
    return json_path, md_path


def main() -> None:
    # Emit Wave-3 setups in the manual scan too (core setups are always on),
    # so the dashboard scan shows the same patterns the auto-trader uses.
    os.environ.setdefault("EWB_WAVE3", "1")
    args = parser().parse_args()
    config = load_watchlist(args.config)
    calibration = load_probability_calibration(args.calibration)
    payload = build_daily_payload(config, calibration)
    json_path, md_path = save_daily_outputs(payload, args.output_dir)
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")


if __name__ == "__main__":
    main()
