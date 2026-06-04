"""Shared helpers for research and backtest scripts."""

from .data import download_ohlc, normalize_ohlc
from .dataset import figure_rows_from_matches
from .logging import log_processing_error
from .portfolio import portfolio_metrics
from .schema import (
    REQUIRED_FIGURE_COLUMNS,
    REQUIRED_TRADE_COLUMNS,
    validate_figure_rows,
    validate_trade_records,
)
from .stats import fmt_df, hypothesis_table, stats_row, t_test
from .trade_metrics import fmt_trade_metrics, trade_metrics
from .trades import exit_for_trade
from .universe import SYMBOLS, cost_for

__all__ = [
    "SYMBOLS",
    "cost_for",
    "download_ohlc",
    "exit_for_trade",
    "figure_rows_from_matches",
    "fmt_df",
    "fmt_trade_metrics",
    "hypothesis_table",
    "log_processing_error",
    "normalize_ohlc",
    "portfolio_metrics",
    "stats_row",
    "t_test",
    "trade_metrics",
    "REQUIRED_FIGURE_COLUMNS",
    "REQUIRED_TRADE_COLUMNS",
    "validate_figure_rows",
    "validate_trade_records",
]
