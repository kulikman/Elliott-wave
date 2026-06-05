"""Rank patterns/timeframes for Anton's stock decision indicator."""
from __future__ import annotations

import json
import os
import sys

import pandas as pd
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ewb.research import portfolio_metrics


REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIGURES = os.path.join(REPO, "python", "data", "figures_all_tfs.parquet")
TRADES = os.path.join(REPO, "python", "data", "trades_sprint6.parquet")
WATCHLIST = os.path.join(REPO, "configs", "watchlist.yaml")
OUT_MD = os.path.join(REPO, "docs", "validation", "anton_pattern_quality_report.md")
OUT_JSON = os.path.join(REPO, "brain-output", "indicator-spec", "anton_pattern_quality_report.json")
TOP_STOCKS_SUMMARY = os.path.join(
    REPO, "brain-output", "signals", "top_stocks_multitf_decision_summary.json"
)

TRADE_PATTERNS = {"flat", "double_corr"}
SKIP_PATTERNS = {"impulse", "triangle"}
HORIZONS = [5, 10, 20, 50, 100]


def load_watchlist() -> list[str]:
    with open(WATCHLIST, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return [str(ticker).upper() for ticker in data.get("tickers", [])]


def pct(value: float | None, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{value * 100:.{digits}f}%"


def money_pct(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value * 100:.2f}%"


def fmt_float(value: float | None, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{value:.{digits}f}"


def ratio(value: float | str | None, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    if isinstance(value, str):
        return value
    return f"{value:.{digits}f}"


def load_optional_json(path: str) -> dict | None:
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def sharpe_like(series: pd.Series) -> float | None:
    series = series.dropna()
    if series.empty or series.std() == 0:
        return None
    return float(series.mean() / series.std())


def confidence_for_n(n: int) -> str:
    if n < 50:
        return "low"
    if n < 150:
        return "medium"
    if n < 400:
        return "high"
    return "very_high"


def action_for_pattern(fig_type: str, direction: str) -> str:
    if fig_type in SKIP_PATTERNS:
        return "WAIT"
    if fig_type not in TRADE_PATTERNS:
        return "WAIT"
    return "SELL" if direction == "up" else "BUY"


def quality_label(n: int, hit: float, mean_ret: float, sh: float | None) -> str:
    if n >= 50 and hit >= 0.58 and mean_ret > 0 and sh is not None and sh >= 0.20:
        return "core"
    if n >= 20 and hit >= 0.55 and mean_ret > 0 and sh is not None and sh >= 0.10:
        return "candidate"
    if mean_ret > 0 and hit > 0.50:
        return "research"
    return "avoid"


def figure_forward_rows(figures: pd.DataFrame, tickers: list[str] | None = None) -> list[dict]:
    stock_figs = figures[figures["ticker"].isin(tickers)].copy() if tickers else figures.copy()
    rows = []
    for fig_type, interval, horizon in [
        (ft, itv, h)
        for ft in sorted(stock_figs["fig_type"].dropna().unique())
        for itv in ["15m", "30m", "1h", "4h", "1d", "1w"]
        for h in HORIZONS
    ]:
        col = f"signed_ret_{horizon}"
        if col not in stock_figs:
            continue
        sub = stock_figs[(stock_figs["fig_type"] == fig_type) & (stock_figs["interval"] == interval)]
        s = sub[col].dropna()
        if len(s) < 10:
            continue
        hit = float((s > 0).mean())
        mean_ret = float(s.mean())
        sh = sharpe_like(s)
        rows.append({
            "fig_type": fig_type,
            "interval": interval,
            "horizon": horizon,
            "n": int(len(s)),
            "hit_rate": hit,
            "mean_return": mean_ret,
            "sharpe_like": sh,
            "confidence": confidence_for_n(len(s)),
            "action": "fade" if fig_type in TRADE_PATTERNS else "wait",
            "quality": quality_label(len(s), hit, mean_ret, sh),
        })
    return sorted(
        rows,
        key=lambda r: (
            {"core": 0, "candidate": 1, "research": 2, "avoid": 3}[r["quality"]],
            -float(r["sharpe_like"] or -999),
            -r["n"],
        ),
    )


def trade_rows(trades: pd.DataFrame, tickers: list[str] | None = None) -> list[dict]:
    stock_trades = trades[trades["ticker"].isin(tickers)].copy() if tickers else trades.copy()
    rows = []
    group_cols = ["fig_type", "interval", "side"]
    for keys, sub in stock_trades.groupby(group_cols, dropna=False):
        fig_type, interval, side = keys
        if len(sub) < 10:
            continue
        m = portfolio_metrics(sub.to_dict("records"))
        net = sub["net_ret"].dropna()
        hit = float((net > 0).mean()) if len(net) else 0.0
        mean_ret = float(net.mean()) if len(net) else 0.0
        sh = sharpe_like(net)
        rows.append({
            "fig_type": fig_type,
            "interval": interval,
            "side": side,
            "n": int(len(sub)),
            "win_rate": hit,
            "ev": mean_ret,
            "sharpe_like": sh,
            "portfolio_sharpe": None if not m else float(m["sharpe"]),
            "max_dd": None if not m else float(m["dd"]),
            "confidence": confidence_for_n(len(sub)),
            "quality": quality_label(len(sub), hit, mean_ret, sh),
        })
    return sorted(
        rows,
        key=lambda r: (
            {"core": 0, "candidate": 1, "research": 2, "avoid": 3}[r["quality"]],
            -float(r["portfolio_sharpe"] or r["sharpe_like"] or -999),
            -r["n"],
        ),
    )


def forward_decision(row: dict) -> str:
    if row["fig_type"] not in TRADE_PATTERNS:
        return "WAIT"
    if row["quality"] == "core":
        return "TRADE fade"
    if row["quality"] == "candidate" and row["confidence"] != "low":
        return "TRADE candidate"
    if row["quality"] in {"candidate", "research"}:
        return "RESEARCH"
    return "WAIT"


def trade_decision(row: dict) -> str:
    if row["fig_type"] not in TRADE_PATTERNS:
        return "WAIT"
    if row["quality"] == "core":
        return "TRADE"
    if (
        row["quality"] == "candidate"
        and row["n"] >= 30
        and row["portfolio_sharpe"] is not None
        and row["portfolio_sharpe"] > 1.0
    ):
        return "TRADE small-size"
    if row["quality"] in {"candidate", "research"}:
        return "RESEARCH"
    return "WAIT"


def md_forward_table(rows: list[dict], limit: int = 20) -> list[str]:
    lines = [
        "| Pattern | TF | Horizon | n | Hit | Mean | Sharpe-like | Conf | Decision |",
        "|---|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for r in rows[:limit]:
        lines.append(
            f"| {r['fig_type']} | {r['interval']} | {r['horizon']} | {r['n']} | "
            f"{pct(r['hit_rate'])} | {money_pct(r['mean_return'])} | "
            f"{fmt_float(r['sharpe_like'])} | {r['confidence']} | {forward_decision(r)} |"
        )
    return lines


def md_trade_table(rows: list[dict], limit: int = 20) -> list[str]:
    lines = [
        "| Pattern | TF | Side | n | Win | EV | Sharpe-like | Portfolio Sharpe | DD | Conf | Decision |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for r in rows[:limit]:
        lines.append(
            f"| {r['fig_type']} | {r['interval']} | {r['side']} | {r['n']} | "
            f"{pct(r['win_rate'])} | {money_pct(r['ev'])} | "
            f"{fmt_float(r['sharpe_like'])} | "
            f"{fmt_float(r['portfolio_sharpe'])} | "
            f"{'n/a' if r['max_dd'] is None else pct(r['max_dd'])} | "
            f"{r['confidence']} | {trade_decision(r)} |"
        )
    return lines


def md_alltf_rows(rows: list[dict], limit: int = 10) -> list[str]:
    lines = [
        "| Pattern | TF | Mode | MTF | n | Win | Mean | PF | Sharpe-trade | TP | SL | Avg bars |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows[:limit]:
        lines.append(
            f"| {r['fig_type']} | {r['interval']} | {r['mode']} | {r['mtf_policy']} | "
            f"{r['n']} | {pct(r['win'])} | {money_pct(r['mean'])} | {ratio(r.get('pf'))} | "
            f"{fmt_float(r.get('sharpe_trade'))} | {pct(r.get('tp_rate'))} | "
            f"{pct(r.get('sl_rate'))} | {fmt_float(r.get('avg_bars'))} |"
        )
    return lines


def md_portfolio_variants(rows: list[dict]) -> list[str]:
    lines = [
        "| Variant | n | CAGR | Sharpe | DD | Calmar | Win | Final |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        lines.append(
            f"| {r['name']} | {r['n']} | {pct(r['cagr'])} | {fmt_float(r['sharpe'])} | "
            f"{pct(r['dd'])} | {fmt_float(r['calmar'])} | {pct(r['win'])} | "
            f"${r['final']:,.0f} |"
        )
    return lines


def main() -> None:
    tickers = load_watchlist()
    figures = pd.read_parquet(FIGURES)
    trades = pd.read_parquet(TRADES)
    forward = figure_forward_rows(figures, tickers)
    trade_quality = trade_rows(trades, tickers)
    trade_quality_all = trade_rows(trades)
    top_stocks = load_optional_json(TOP_STOCKS_SUMMARY)

    n_assets = int(figures["ticker"].nunique())
    intervals = ", ".join(str(x) for x in sorted(figures["interval"].dropna().unique()))
    watchlist_figures = figures[figures["ticker"].isin(tickers)]
    watchlist_trades = trades[trades["ticker"].isin(tickers)]

    payload = {
        "watchlist": tickers,
        "figures_rows": int(len(figures)),
        "trades_rows": int(len(trades)),
        "forward": forward,
        "trade_quality": trade_quality,
        "trade_quality_all_symbols": trade_quality_all,
        "top_stocks_multitf_summary": top_stocks,
    }
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")

    lines = [
        "# Anton pattern quality report",
        "",
        "Цель: найти паттерны и таймфреймы, которые помогают Антону принимать решения `BUY / SELL / WAIT` на акциях.",
        "",
        f"Watchlist: `{', '.join(tickers)}`",
        f"Исторических фигур: `{len(figures)}` по `{n_assets}` активам; TF: `{intervals}`.",
        f"Фильтр отчёта: `{len(tickers)}` акций watchlist: `{len(watchlist_figures)}` фигур.",
        f"TP/SL сделок sprint6: `{len(trades)}` всего; по watchlist: `{len(watchlist_trades)}`.",
        "В TP/SL таблицах показаны только группы с `n >= 10`.",
        "",
        "## Короткий вывод",
        "",
        "- Рабочая торговая база остаётся прежней: `flat` и `double_corr` торгуются fade-направлением.",
        "- `impulse` и `triangle` не должны давать вход: их роль в индикаторе — `WAIT / context`.",
        "- По watchlist лучший подтверждённый TP/SL сигнал сейчас — `flat 1h long`: `TRADE small-size`, не агрессивный `all-in`.",
        "- `double_corr` часто даёт лучший forward edge, но по watchlist TP/SL выборка мала; это сильный research-кандидат, не `A`-сигнал.",
        "- `flat` даёт больше наблюдений и стабильнее подходит для ежедневного рабочего сигнала, но short-сторону нужно фильтровать.",
        "",
        "## Лучшие forward-return комбинации по акциям watchlist",
        "",
    ]
    lines.extend(md_forward_table([r for r in forward if r["fig_type"] in TRADE_PATTERNS and r["quality"] in {"core", "candidate", "research"}], 25))
    lines.extend([
        "",
        "## TP/SL качество по акциям watchlist",
        "",
    ])
    lines.extend(md_trade_table(trade_quality, 25))
    lines.extend([
        "",
        "## TP/SL reference по всем 58 активам",
        "",
        "Эта таблица нужна для калибровки индикатора, но решение по деньгам Антона должно учитывать watchlist-таблицу выше.",
        "",
    ])
    lines.extend(md_trade_table([r for r in trade_quality_all if r["fig_type"] in TRADE_PATTERNS], 20))
    if top_stocks:
        best_tradable = [
            r for r in top_stocks.get("best_rows", [])
            if r.get("fig_type") in TRADE_PATTERNS
        ]
        lines.extend([
            "",
            "## All-TF тест на крупных ликвидных акциях",
            "",
            f"Источник: `docs/validation/top_stocks_multitf_decision_test.md`, generated `{top_stocks.get('generated_at')}`.",
            f"Universe: `{', '.join(top_stocks.get('universe', []))}`.",
            f"Сделочных строк: `{top_stocks.get('n_rows')}`, базовых сигналов: `{top_stocks.get('n_unique_base_signals_estimate')}`.",
            "",
            "### Лучшие строки Flat/DoubleCorr",
            "",
        ])
        lines.extend(md_alltf_rows(best_tradable, 8))
        lines.extend([
            "",
            "### Портфельные варианты",
            "",
        ])
        lines.extend(md_portfolio_variants(top_stocks.get("portfolio_variants", [])))
        lines.extend([
            "",
            "All-TF вывод: лучший баланс сейчас у `Flat+DC fade 1h+4h+1d / no HTF`; жёсткий Pine HTF-фильтр снижает доходность, хотя повышает win-rate.",
            "",
        ])
    lines.extend([
        "",
        "## Что считать идеальным паттерном для v0",
        "",
        "1. `flat 1h/4h fade`: основной практический класс сигналов; `flat 1h long` лучший по watchlist, `flat 4h fade` лучший в all-TF тесте.",
        "2. `flat 1h short`: не самостоятельный идеальный сигнал по watchlist; нужен дополнительный фильтр тренда/MTF или `WAIT`.",
        "3. `double_corr 1h/4h fade`: сильный кандидат с хорошим портфельным поведением, но показывать с пониженной confidence из-за малого `N`.",
        "4. `flat 1d/4h`: использовать как старший контекст и более спокойный setup, не как шумный частый сигнал.",
        "5. `15m/30m`: research/scalping зона; по умолчанию не включать на графике Антона, чтобы убрать шум.",
        "6. `impulse` и `triangle`: не торговать в v0, использовать только как причину `WAIT`.",
        "",
        "## Правило для индикатора Антона",
        "",
        "- `BUY`: fresh `flat/double_corr` fade long, не late, поддержанный risk/reward и market mode; strongest now: `flat 1h long`.",
        "- `SELL`: fresh `flat/double_corr` fade short только с дополнительным фильтром качества; иначе `WAIT`.",
        "- `WAIT`: target passed, stop hit, stale, late entry, unsupported market, `impulse`, `triangle`, либо низкое качество группы.",
        "- `EXIT`: target = полный ретрейс/цель фигуры; stop = амплитуда фигуры; после прохождения target вход запрещён.",
        "",
        "## Следующий шаг",
        "",
        "Перевести MTF в score/penalty-фильтр и повторить отчёт: старший TF должен снижать confidence, но не быть жёстким блоком по умолчанию.",
        "",
    ])
    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(OUT_MD)
    print(OUT_JSON)


if __name__ == "__main__":
    main()
