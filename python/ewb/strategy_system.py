"""Strategy-system helpers around the EWB TradingView indicator.

The indicator is the visual/alert surface. This module is the audit surface:
it normalizes historical research trades, records forward alert events, and
compares live outcomes with historical expectations.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


TRADE_PATTERNS = {"flat", "double_corr"}
DEFAULT_FORWARD_LOG = Path("python/data/forward_signals/ewb_forward_events.jsonl")
DEFAULT_BACKTEST_DIR = Path("brain-output/backtests")
CRYPTO_BASES = {
    "AAVE", "ADA", "ARB", "ATOM", "AVAX", "BCH", "BNB", "BTC", "DOGE",
    "DOT", "ETC", "ETH", "FIL", "HBAR", "ICP", "LINK", "LTC", "NEAR",
    "OP", "PEPE", "POL", "SHIB", "SOL", "SUI", "TON", "TRX", "UNI",
    "WIF", "XLM", "XRP",
}
CRYPTO_EXCHANGES = {
    "BINANCE", "BITFINEX", "BITSTAMP", "BYBIT", "COINBASE", "CRYPTO",
    "GEMINI", "KRAKEN", "KUCOIN", "OKX",
}


@dataclass(frozen=True)
class StrategyContract:
    """Versioned bot contract that turns indicator signals into testable trades."""

    strategy_id: str = "ewb-anton-v1"
    entry_rule: str = "confirm_close_or_alert_close"
    exit_rule: str = "tp_sl_time"
    allowed_patterns: tuple[str, ...] = ("flat", "double_corr")
    allowed_actions: tuple[str, ...] = ("long", "short")
    required_htf_context: str = "record_only"
    notes: str = (
        "Python reports are source of truth for statistics; Pine is visual and alert surface."
    )


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_signal_id(parts: Iterable[Any]) -> str:
    raw = "|".join("" if part is None else str(part) for part in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def side_to_int(side: str) -> int:
    return 1 if str(side).lower() in {"long", "buy", "enter long"} else -1


def probability_percent(value: Any) -> float | None:
    """Normalize probability input into the 0..100 percentage scale."""
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except Exception:
        return None
    if not math.isfinite(number):
        return None
    if 0.0 <= number <= 1.0:
        number *= 100.0
    return number


def _symbol_leaf(symbol: Any) -> str:
    return str(symbol or "").strip().upper().split(":")[-1]


def _compact_symbol(symbol: Any) -> str:
    return (
        _symbol_leaf(symbol)
        .replace("-", "")
        .replace("/", "")
        .replace("_", "")
        .replace(" ", "")
    )


def is_crypto_ticker(ticker: Any) -> bool:
    """Detect common stock-data and TradingView crypto symbol formats."""
    raw = str(ticker or "").strip().upper()
    if not raw:
        return False
    if ":" in raw and raw.split(":", 1)[0] in CRYPTO_EXCHANGES:
        return True
    compact = _compact_symbol(raw)
    for quote in ("USDT", "USDC", "USD", "PERP"):
        if compact.endswith(quote):
            base = compact[: -len(quote)]
            return base in CRYPTO_BASES
    return compact in CRYPTO_BASES


def setup_key(row: pd.Series | dict[str, Any]) -> str:
    get = row.get if isinstance(row, dict) else row.get
    return "|".join([
        str(get("asset_class", "stock")),
        str(get("interval", "")),
        str(get("fig_type", "")),
        str(get("side", "")),
        str(get("mtf_policy", "none")),
        str(get("entry_variant", "confirm_close")),
    ])


def normalize_historical_trades(trades: pd.DataFrame, asset_class: str | None = None) -> pd.DataFrame:
    """Normalize historical grid trades into the strategy-system contract."""
    if trades.empty:
        return pd.DataFrame()

    out = trades.copy()
    if "asset_class" not in out.columns:
        out["asset_class"] = asset_class or "stock"
    elif asset_class:
        out["asset_class"] = out["asset_class"].fillna(asset_class)

    for col in ("entry_ts", "exit_ts"):
        if col in out.columns:
            out[col] = pd.to_datetime(out[col], utc=True, errors="coerce")

    if "strategy_id" not in out.columns:
        out["strategy_id"] = StrategyContract().strategy_id
    out["setup_key"] = out.apply(setup_key, axis=1)
    if "signal_id" not in out.columns:
        out["signal_id"] = out.apply(
            lambda row: stable_signal_id([
                row.get("ticker"), row.get("interval"), row.get("fig_type"),
                row.get("side"), row.get("entry_ts"), row.get("entry_px"),
            ]),
            axis=1,
        )
    if "win" in out.columns:
        out["win"] = out["win"].astype(bool)
    if "net_ret" in out.columns:
        out["net_ret"] = pd.to_numeric(out["net_ret"], errors="coerce")
    return out


def filter_contract_trades(
    trades: pd.DataFrame,
    contract: StrategyContract | None = None,
    min_model_p: float | None = None,
    min_sample: int | None = None,
    intervals: set[str] | None = None,
    universe_limit: int | None = None,
    entry_variants: set[str] | None = None,
    mtf_policies: set[str] | None = None,
    late_limit: float | None = None,
    tp_mult: float | None = None,
    sl_mult: float | None = None,
    exit_plan: str | None = None,
) -> pd.DataFrame:
    """Apply the default bot contract filters to historical trades."""
    contract = contract or StrategyContract()
    if trades.empty:
        return trades.copy()
    out = trades.copy()
    out = out[out["fig_type"].isin(contract.allowed_patterns)]
    out = out[out["side"].isin(contract.allowed_actions)]
    if intervals:
        out = out[out["interval"].isin(intervals)]
    if universe_limit is not None and "universe_rank" in out.columns:
        out = out[out["universe_rank"] <= universe_limit]
    if entry_variants and "entry_variant" in out.columns:
        out = out[out["entry_variant"].isin(entry_variants)]
    if mtf_policies and "mtf_policy" in out.columns:
        out = out[out["mtf_policy"].isin(mtf_policies)]
    if late_limit is not None and "late_limit" in out.columns:
        out = out[pd.to_numeric(out["late_limit"], errors="coerce") == late_limit]
    if tp_mult is not None and "tp_mult" in out.columns:
        out = out[pd.to_numeric(out["tp_mult"], errors="coerce") == tp_mult]
    if sl_mult is not None and "sl_mult" in out.columns:
        out = out[pd.to_numeric(out["sl_mult"], errors="coerce") == sl_mult]
    if exit_plan and "exit_plan" in out.columns:
        out = out[out["exit_plan"] == exit_plan]
    if min_model_p is not None and "p_win_model" in out.columns:
        out = out[pd.to_numeric(out["p_win_model"], errors="coerce") >= min_model_p]
    if min_sample is not None and "sample_size" in out.columns:
        out = out[pd.to_numeric(out["sample_size"], errors="coerce") >= min_sample]
    return out


def trade_summary(trades: pd.DataFrame, return_col: str = "net_ret") -> dict[str, Any]:
    """Calculate bot-level trade metrics."""
    if trades.empty or return_col not in trades.columns:
        return {
            "trades": 0,
            "winrate": math.nan,
            "expectancy": math.nan,
            "profit_factor": math.nan,
            "max_drawdown": math.nan,
            "avg_return": math.nan,
            "median_return": math.nan,
        }

    returns = pd.to_numeric(trades[return_col], errors="coerce").dropna()
    scoped = trades.loc[returns.index].copy()
    if returns.empty:
        return trade_summary(pd.DataFrame(), return_col)
    wins = scoped["win"].astype(bool) if "win" in scoped.columns else returns > 0
    gross_win = returns[wins].sum()
    gross_loss = returns[~wins].sum()
    safe_returns = returns.clip(lower=-0.999999, upper=10.0)
    log_equity = np.log1p(safe_returns).cumsum()
    log_peak = log_equity.cummax()
    drawdown = np.exp(log_equity - log_peak) - 1.0
    total_log_return = float(log_equity.iloc[-1]) if len(log_equity) else math.nan
    return {
        "trades": int(len(returns)),
        "winrate": float(wins.mean()),
        "expectancy": float(returns.mean()),
        "profit_factor": float(-gross_win / gross_loss) if gross_loss < 0 else math.nan,
        "max_drawdown": float(drawdown.min()) if len(drawdown) else math.nan,
        "avg_return": float(returns.mean()),
        "median_return": float(returns.median()),
        "total_return": float(math.exp(total_log_return) - 1.0) if total_log_return < 700 else math.inf,
        "avg_win": float(returns[wins].mean()) if wins.any() else 0.0,
        "avg_loss": float(returns[~wins].mean()) if (~wins).any() else 0.0,
    }


def grouped_summary(trades: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if trades.empty:
        return pd.DataFrame()
    for keys, grp in trades.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(group_cols, keys))
        row.update(trade_summary(grp.sort_values("entry_ts")))
        rows.append(row)
    return pd.DataFrame(rows).sort_values(
        ["profit_factor", "expectancy", "trades"], ascending=[False, False, False]
    )


def walk_forward_summary(
    trades: pd.DataFrame,
    date_col: str = "entry_ts",
    folds: int = 6,
) -> pd.DataFrame:
    """Split chronological trades into forward folds and report each fold."""
    if trades.empty or date_col not in trades.columns:
        return pd.DataFrame()
    scoped = trades.dropna(subset=[date_col]).sort_values(date_col).copy()
    if scoped.empty:
        return pd.DataFrame()
    fold_count = max(1, min(folds, len(scoped)))
    chunks = []
    for fold_no, idx in enumerate(np.array_split(scoped.index, fold_count), start=1):
        grp = scoped.loc[idx]
        row = {
            "fold": fold_no,
            "start": grp[date_col].min().isoformat(),
            "end": grp[date_col].max().isoformat(),
        }
        row.update(trade_summary(grp))
        chunks.append(row)
    return pd.DataFrame(chunks)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists() or path.is_dir():
        return []
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def signal_event(
    *,
    ticker: str,
    interval: str,
    action: str,
    entry_ts: str,
    entry_px: float,
    stop_px: float | None = None,
    target_px: float | None = None,
    fig_type: str = "unknown",
    probability: float | None = None,
    htf_context: str = "",
    signal_id: str | None = None,
    source: str = "manual",
) -> dict[str, Any]:
    side = "long" if action.lower() in {"buy", "long", "enter long"} else "short"
    signal_id = signal_id or stable_signal_id([ticker, interval, side, entry_ts, entry_px])
    row = {
        "event_type": "signal",
        "recorded_at": utc_now_iso(),
        "signal_id": signal_id,
        "source": source,
        "strategy_id": StrategyContract().strategy_id,
        "ticker": ticker.upper(),
        "interval": interval,
        "fig_type": fig_type,
        "side": side,
        "action": action.lower(),
        "entry_ts": pd.Timestamp(entry_ts).isoformat(),
        "entry_px": float(entry_px),
        "stop_px": None if stop_px is None else float(stop_px),
        "target_px": None if target_px is None else float(target_px),
        "probability": probability_percent(probability),
        "htf_context": htf_context,
    }
    row["setup_key"] = setup_key({
        "asset_class": "crypto" if is_crypto_ticker(row["ticker"]) else "stock",
        "interval": interval,
        "fig_type": fig_type,
        "side": side,
        "mtf_policy": "forward_alert",
        "entry_variant": "alert_close",
    })
    return row


def _first_present(payload: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return value
    return None


def signal_event_from_payload(
    payload: dict[str, Any],
    *,
    source: str = "tradingview",
) -> dict[str, Any]:
    """Build a signal event from a TradingView/manual JSON alert payload."""
    ticker = _first_present(payload, ("ticker", "symbol", "syminfo_ticker", "tv_ticker"))
    interval = _first_present(payload, ("interval", "timeframe", "tf"))
    action = _first_present(payload, ("action", "side", "recommendation"))
    entry_ts = _first_present(payload, ("entry_ts", "time", "timestamp", "bar_time"))
    entry_px = _first_present(payload, ("entry_px", "entry", "price", "close"))
    missing = [
        name
        for name, value in {
            "ticker": ticker,
            "interval": interval,
            "action": action,
            "entry_ts": entry_ts,
            "entry_px": entry_px,
        }.items()
        if value in (None, "")
    ]
    if missing:
        raise ValueError("Missing required alert fields: " + ", ".join(missing))

    return signal_event(
        ticker=str(ticker),
        interval=str(interval),
        action=str(action),
        entry_ts=str(entry_ts),
        entry_px=float(entry_px),
        stop_px=_first_present(payload, ("stop_px", "stop", "sl")),
        target_px=_first_present(payload, ("target_px", "target", "tp")),
        fig_type=str(_first_present(payload, ("fig_type", "pattern", "structure")) or "unknown"),
        probability=_first_present(payload, ("probability", "p", "p_win", "p_trade_win")),
        htf_context=str(_first_present(payload, ("htf_context", "context", "mtf_context")) or ""),
        signal_id=_first_present(payload, ("signal_id", "id")),
        source=str(payload.get("source") or source),
    )


def outcome_event(
    *,
    signal_id: str,
    exit_ts: str,
    exit_px: float,
    exit_reason: str,
) -> dict[str, Any]:
    return {
        "event_type": "outcome",
        "recorded_at": utc_now_iso(),
        "signal_id": signal_id,
        "exit_ts": pd.Timestamp(exit_ts).isoformat(),
        "exit_px": float(exit_px),
        "exit_reason": exit_reason,
    }


def note_event(
    *,
    signal_id: str,
    note: str,
    tag: str = "note",
    author: str = "anton",
) -> dict[str, Any]:
    return {
        "event_type": "note",
        "recorded_at": utc_now_iso(),
        "signal_id": signal_id,
        "tag": tag,
        "author": author,
        "note": note,
    }


def forward_trades(events: list[dict[str, Any]]) -> pd.DataFrame:
    """Reconstruct closed/open forward trades from signal/outcome events."""
    signals = {row["signal_id"]: row for row in events if row.get("event_type") == "signal"}
    outcomes = {row["signal_id"]: row for row in events if row.get("event_type") == "outcome"}
    rows = []
    for signal_id, signal in signals.items():
        row = dict(signal)
        outcome = outcomes.get(signal_id)
        if outcome:
            row.update(outcome)
            if str(row.get("exit_reason", "")).lower() == "cancelled":
                row["raw_ret"] = math.nan
                row["net_ret"] = math.nan
                row["win"] = False
                row["status"] = "cancelled"
            else:
                side = side_to_int(row.get("side", "long"))
                entry = float(row["entry_px"])
                exit_px = float(row["exit_px"])
                raw_ret = side * (exit_px - entry) / entry if entry else math.nan
                row["raw_ret"] = raw_ret
                row["net_ret"] = raw_ret
                row["win"] = raw_ret > 0
                row["status"] = "closed"
        else:
            row["status"] = "open"
        rows.append(row)
    out = pd.DataFrame(rows)
    for col in ("entry_ts", "exit_ts", "recorded_at"):
        if col in out.columns:
            out[col] = pd.to_datetime(out[col], utc=True, errors="coerce")
    return out


def pct(value: float | None, digits: int = 1) -> str:
    if value is None or not math.isfinite(float(value)):
        return "n/a"
    return f"{float(value) * 100:.{digits}f}%"


def num(value: float | None, digits: int = 2) -> str:
    if value is None or not math.isfinite(float(value)):
        return "n/a"
    return f"{float(value):.{digits}f}"


def markdown_table(rows: list[dict[str, Any]], columns: list[tuple[str, str]], limit: int = 20) -> str:
    header = "| " + " | ".join(title for title, _ in columns) + " |"
    sep = "|" + "|".join("---" for _ in columns) + "|"
    lines = [header, sep]
    for row in rows[:limit]:
        vals = []
        for _, key in columns:
            value = row.get(key)
            if key in {"winrate", "expectancy", "max_drawdown", "avg_return", "median_return", "total_return"}:
                vals.append(pct(value, 2 if key in {"expectancy", "avg_return", "median_return"} else 1))
            elif key == "profit_factor":
                vals.append(num(value, 2))
            else:
                vals.append(str(value))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def write_frame(df: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        df.to_parquet(path, index=False)
        return path
    except Exception:
        csv_path = path.with_suffix(".csv")
        df.to_csv(csv_path, index=False)
        return csv_path


def contract_payload(contract: StrategyContract | None = None) -> dict[str, Any]:
    return asdict(contract or StrategyContract())
