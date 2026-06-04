"""Schema checks for research/backtest records."""
from __future__ import annotations


REQUIRED_TRADE_COLUMNS = {
    "entry_ts",
    "exit_ts",
    "amp_pct",
    "net_ret",
}

REQUIRED_FIGURE_COLUMNS = {
    "ticker",
    "interval",
    "end_ts",
    "entry_ts",
    "confirmation_lag",
    "fig_type",
    "direction",
    "amp_pct",
    "htf_bias",
    "with_htf",
    "against_htf",
    "entry_px",
}


def validate_trade_records(trades) -> None:
    """Validate the minimal trade schema needed by portfolio simulation."""
    if len(trades) == 0:
        return
    first = trades[0] if isinstance(trades, list) else None
    columns = set(first.keys()) if first is not None else set(getattr(trades, "columns", []))
    missing = sorted(REQUIRED_TRADE_COLUMNS - columns)
    if missing:
        raise ValueError(f"trade records missing required columns: {', '.join(missing)}")


def validate_figure_rows(rows, horizons=(5, 10, 20, 50, 100)) -> None:
    """Validate dataset rows before parquet export."""
    if len(rows) == 0:
        return
    first = rows[0] if isinstance(rows, list) else None
    columns = set(first.keys()) if first is not None else set(getattr(rows, "columns", []))
    required = set(REQUIRED_FIGURE_COLUMNS)
    for horizon in horizons:
        required.add(f"ret_{horizon}")
        required.add(f"signed_ret_{horizon}")
    missing = sorted(required - columns)
    if missing:
        raise ValueError(f"figure rows missing required columns: {', '.join(missing)}")
