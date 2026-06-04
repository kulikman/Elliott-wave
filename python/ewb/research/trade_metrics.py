"""Per-trade return metrics for backtest reports."""
from __future__ import annotations

import numpy as np
import pandas as pd


def trade_metrics(trades: pd.DataFrame, key: str = "net_ret") -> dict:
    """Calculate simple compounded metrics over a trade table."""
    if trades.empty:
        return {}
    returns = trades[key]
    wins = trades["win"]
    mean = returns.mean()
    std = returns.std()
    sorted_trades = trades.sort_values("entry_ts")
    equity = (1 + sorted_trades[key]).cumprod()
    peak = equity.cummax()
    drawdown = (equity / peak - 1).min()
    total_ret = equity.iloc[-1] - 1 if len(equity) else 0
    return {
        "n_trades": len(trades),
        "win_rate": wins.mean(),
        "mean_ret": mean,
        "median_ret": returns.median(),
        "std_ret": std,
        "total_ret": total_ret,
        "sharpe_naive": mean / std * np.sqrt(252) if std > 0 else np.nan,
        "max_dd": drawdown,
        "calmar": total_ret / abs(drawdown) if drawdown != 0 else np.nan,
        "avg_win": returns[wins].mean() if wins.any() else 0,
        "avg_loss": returns[~wins].mean() if (~wins).any() else 0,
        "profit_factor": (
            -returns[wins].sum() / returns[~wins].sum()
            if (~wins).any() and returns[~wins].sum() < 0
            else np.nan
        ),
    }


def fmt_trade_metrics(metrics: dict) -> str:
    """Format trade metrics for legacy Sprint 6 reports."""
    return (f"n={metrics['n_trades']}, win={metrics['win_rate']*100:.1f}%, "
            f"mean={metrics['mean_ret']*100:.2f}%, total={metrics['total_ret']*100:.1f}%, "
            f"DD={metrics['max_dd']*100:.1f}%, Sharpe~{metrics['sharpe_naive']:.2f}, "
            f"PF={metrics['profit_factor']:.2f}, "
            f"avg W/L={metrics['avg_win']*100:.2f}%/{metrics['avg_loss']*100:.2f}%")
