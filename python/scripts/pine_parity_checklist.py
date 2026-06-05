"""Build a manual Python-vs-Pine parity checklist from the daily report."""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.scan_probability_signals import fmt_px, money_pct, pct


REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_REPORT = os.path.join(REPO, "brain-output", "signals", "daily_report.json")
DEFAULT_OUTPUT = os.path.join(REPO, "docs", "pine_parity_checklist.md")
DEFAULT_CRYPTO_TRADES = os.path.join(
    REPO, "python", "data", "historical_signal_grid_crypto_trades.parquet"
)
DEFAULT_CRYPTO_OUTPUT = os.path.join(REPO, "docs", "pine_parity_crypto_checklist.md")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--asset-class", choices=["stocks", "crypto"], default="stocks")
    p.add_argument("--report", default=DEFAULT_REPORT, help="daily_report.json path")
    p.add_argument("--trades", default=DEFAULT_CRYPTO_TRADES, help="Crypto grid trades parquet path")
    p.add_argument("--output", default=DEFAULT_OUTPUT, help="Markdown output path")
    p.add_argument("--limit", type=int, default=24, help="Max crypto rows to include")
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


def side_action(side: str) -> str:
    if side == "long":
        return "BUY"
    if side == "short":
        return "SELL"
    return "WAIT"


def trade_level(row: pd.Series, level: str) -> float | None:
    entry = row.get("entry_px")
    amp_pct = row.get("amp_pct")
    if entry is None or amp_pct is None or pd.isna(entry) or pd.isna(amp_pct):
        return None
    amp = float(entry) * float(amp_pct)
    side = row.get("side")
    if level == "entry":
        return float(entry)
    if level == "target":
        mult = float(row.get("tp_mult", 1.0))
        return float(entry) + amp * mult if side == "long" else float(entry) - amp * mult
    if level == "stop":
        mult = float(row.get("sl_mult", 1.0))
        return float(entry) - amp * mult if side == "long" else float(entry) + amp * mult
    return None


def crypto_trade_row(row: pd.Series, note: str) -> str:
    p_win = row.get("p_win_model")
    p_win_fraction = None if p_win is None or pd.isna(p_win) else float(p_win) / 100.0
    return (
        f"| {row.get('ticker', 'n/a')} | {row.get('interval', 'n/a')} | "
        f"{row.get('entry_ts', 'n/a')} | {row.get('fig_type', 'n/a')} | "
        f"{side_action(str(row.get('side', '')))} | WAIT / crypto research | "
        f"{pct(p_win_fraction)} / {money_pct(row.get('model_ev'))} | "
        f"{fmt_px(trade_level(row, 'entry'))} | {fmt_px(trade_level(row, 'stop'))} | "
        f"{fmt_px(trade_level(row, 'target'))} | {note} |"
    )


def representative_crypto_rows(trades: pd.DataFrame, limit: int) -> pd.DataFrame:
    filtered = trades[
        (trades["asset_class"] == "crypto")
        & (trades["fig_type"].isin(["flat", "double_corr", "impulse", "triangle"]))
        & (trades["entry_variant"] == "confirm_close")
        & (trades["mtf_policy"] == "none")
        & (trades["tp_mult"] == 1.0)
        & (trades["sl_mult"] == 1.0)
        & (trades["exit_plan"] == "full")
    ].copy()
    if filtered.empty:
        return filtered
    filtered["entry_ts_sort"] = pd.to_datetime(filtered["entry_ts"], utc=True, errors="coerce")
    filtered = filtered.sort_values(["entry_ts_sort", "ticker", "interval"], ascending=[False, True, True])
    grouped = filtered.groupby(["ticker", "interval", "fig_type", "side"], as_index=False).head(1)
    return grouped.head(limit)


def build_crypto_markdown(trades: pd.DataFrame, limit: int, source_path: str) -> str:
    rows = representative_crypto_rows(trades, limit)
    generated_at = "n/a"
    if not rows.empty:
        generated_at = str(rows["entry_ts"].max())
    lines = [
        "# Pine crypto parity checklist",
        "",
        f"Источник: `{source_path}`",
        f"Последняя строка Python: `{generated_at}`",
        "Модель: `probability-calibration-crypto-v0` / research-only",
        "",
        "Цель: вручную проверить, что Pine на crypto-графиках не использует stock-калибровку",
        "как рабочий BUY/SELL. Crypto пока должен оставаться `WAIT / crypto research`, пока",
        "отдельная crypto parity не станет production-ready.",
        "",
        "Как проверять:",
        "1. Открой crypto ticker в TradingView, например `BTCUSDT`, `ETHUSDT`, `SOLUSDT`.",
        "2. Поставь TF из таблицы.",
        "3. В `Elliott Wave Brain — Monowaves MTF` выставь `Market mode = Crypto`.",
        "4. Ожидаемый результат: `Action now = WAIT`, `Reason = CRYPTO RESEARCH ONLY`, `Market = Crypto / crypto-v0 research`.",
        "5. В `Market mode = Stocks` тот же график должен показывать `WAIT / unsupported crypto`.",
        "6. Убедись, что BUY/SELL alerts не срабатывают на crypto.",
        "",
        "## Crypto research rows",
        "",
        "| Тикер | TF | Python entry_ts | Pattern | Python side | Ожидаемый Action now | P/EV | Entry | Stop | Target | Проверка |",
        "|---|---|---|---|---|---|---:|---:|---:|---:|---|",
    ]
    if rows.empty:
        lines.append("| n/a | n/a | n/a | n/a | n/a | WAIT / crypto research | n/a | n/a | n/a | n/a | crypto rows not found |")
    else:
        for _, row in rows.iterrows():
            lines.append(crypto_trade_row(row, "Pine не должен превращать это в рабочий BUY/SELL"))

    lines.extend([
        "",
        "## Критерии прохождения",
        "",
        "- На crypto-графике `Action now` остаётся `WAIT` независимо от найденной фигуры.",
        "- Панель явно показывает `crypto-v0 research`, а не `stocks-v0`.",
        "- `P≈`, `Entry / TP`, `SL` не выглядят как рабочий stock trade-plan для crypto.",
        "- `alertcondition` BUY/SELL не срабатывает для crypto.",
        "- Если Pine и Python по фигуре расходятся, это finding для будущей crypto parity, но не причина включать crypto-сделки.",
        "",
    ])
    return "\n".join(lines)


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
    if args.asset_class == "crypto":
        trades = pd.read_parquet(args.trades)
        markdown = build_crypto_markdown(trades, args.limit, args.trades)
        if args.output == DEFAULT_OUTPUT:
            args.output = DEFAULT_CRYPTO_OUTPUT
    else:
        report = load_report(args.report)
        markdown = build_markdown(report)
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(markdown)
    print(args.output)


if __name__ == "__main__":
    main()
