"""Build a manual Python-vs-Pine parity checklist from the daily report."""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.scan_probability_signals import fmt_px, money_pct, pct


REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_REPORT = os.path.join(REPO, "brain-output", "signals", "daily_report.json")
DEFAULT_OUTPUT = os.path.join(REPO, "docs", "pine_parity_checklist.md")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--report", default=DEFAULT_REPORT, help="daily_report.json path")
    p.add_argument("--output", default=DEFAULT_OUTPUT, help="Markdown output path")
    return p


def load_report(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def risk_value(signal: dict[str, Any], key: str) -> str:
    return fmt_px((signal.get("risk_box") or {}).get(key))


def expected_action(signal: dict[str, Any]) -> str:
    action = signal.get("recommended_action")
    if action == "buy":
        return "BUY, если в Pine статус ACTIVE и вход не late"
    if action == "sell":
        return "SELL, если в Pine статус ACTIVE и вход не late"
    if action == "skip":
        return "WAIT"
    if action == "wait":
        return "WAIT"
    return "n/a"


def signal_row(signal: dict[str, Any], note: str) -> str:
    return (
        f"| {signal.get('ticker', 'n/a')} | {signal.get('interval', 'n/a')} | "
        f"{signal.get('entry_ts', 'n/a')} | {signal.get('pattern', 'n/a')} | "
        f"{signal.get('recommended_action', 'n/a')} | {expected_action(signal)} | "
        f"{pct(signal.get('p_trade_win'))} / {money_pct(signal.get('expected_net_return'))} | "
        f"{risk_value(signal, 'entry_px')} | {risk_value(signal, 'stop_px')} | "
        f"{risk_value(signal, 'target_px')} | {note} |"
    )


def build_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Pine parity checklist",
        "",
        f"Источник: `brain-output/signals/daily_report.json`",
        f"Сформировано Python: `{report.get('generated_at', 'n/a')}`",
        f"Модель: `{report.get('model_version', 'n/a')}`",
        f"Таймфрейм для TradingView: `{report.get('interval', 'n/a')}`",
        "",
        "Цель: вручную сверить, что Pine на TradingView показывает тот же последний сигнал,",
        "что Python runtime. Это контроль против расхождения Pine-детектора и проверенного Python.",
        "",
        "Как проверять:",
        "1. Открой тикер в TradingView.",
        "2. Поставь таймфрейм из таблицы.",
        "3. Убедись, что `Market mode = Stocks` для акций.",
        "4. Сравни `Last signal`, `Pattern`, `P / EV`, `Entry`, `Stop`, `Target`.",
        "5. `Action now` может стать `WAIT`, если Pine видит `TP passed`, `SL hit`, `STALE` или `late entry`.",
        "",
        "## Свежие торговые сигналы",
        "",
        "| Тикер | TF | Python entry_ts | Pattern | Python action | Ожидаемый Action now | P/EV | Entry | Stop | Target | Проверка |",
        "|---|---|---|---|---|---|---:|---:|---:|---:|---|",
    ]

    signals = report.get("signals") or []
    if signals:
        for signal in signals:
            lines.append(signal_row(signal, "сверить на графике"))
    else:
        lines.append("| n/a | n/a | n/a | n/a | n/a | WAIT | n/a | n/a | n/a | n/a | свежих сигналов нет |")

    last_signals = report.get("last_signal_by_ticker") or {}
    if last_signals:
        lines.extend([
            "",
            "## Последние no-trade наблюдения",
            "",
            "Эти строки не должны давать рабочий вход в Pine. Нормальный результат: `Action now = WAIT`.",
            "",
            "| Тикер | TF | Python entry_ts | Pattern | Python action | Ожидаемый Action now | P/EV | Entry | Stop | Target | Проверка |",
            "|---|---|---|---|---|---|---:|---:|---:|---:|---|",
        ])
        for ticker in sorted(last_signals):
            lines.append(signal_row(last_signals[ticker], "должно быть WAIT/no-trade"))

    lines.extend([
        "",
        "## Критерии прохождения",
        "",
        "- `Pattern` совпадает с Python или расхождение занесено в backlog Pine parity.",
        "- `Last signal` совпадает по стороне: `buy -> BUY`, `sell -> SELL`, `skip/wait -> WAIT`.",
        "- `Entry`, `Stop`, `Target` отличаются только на округление цены.",
        "- Для crypto при `Market mode = Stocks` Pine должен показывать `WAIT / unsupported market`.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    args = parser().parse_args()
    report = load_report(args.report)
    markdown = build_markdown(report)
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(markdown)
    print(args.output)


if __name__ == "__main__":
    main()
