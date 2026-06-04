"""Statistical helpers for edge discovery reports."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def t_test(series: pd.Series, min_n: int = 10) -> tuple[float, float]:
    """One-sample t-test against zero, with a minimum sample guard."""
    s = series.dropna()
    if len(s) < min_n:
        return np.nan, np.nan
    t, p = stats.ttest_1samp(s, 0)
    return t, p


def stats_row(series: pd.Series, label: str | None = None,
              min_n: int = 1) -> dict | None:
    """Return common edge metrics for a return series."""
    s = series.dropna()
    if len(s) < min_n:
        return None
    t, p = t_test(s)
    row = {
        "n": len(s),
        "hit_rate": (s > 0).mean(),
        "mean_ret": s.mean(),
        "std_ret": s.std(),
        "sharpe": s.mean() / s.std() if s.std() > 0 else np.nan,
        "t_stat": t,
        "p_value": p,
    }
    if label is not None:
        row["group"] = label
    return row


def hypothesis_table(df: pd.DataFrame, groupby, horizon: int, signal_col: str,
                     min_n: int = 5) -> pd.DataFrame:
    """Per-group hit rate / mean / Sharpe / t-stat / p-value / n."""
    rows = []
    group_cols = groupby if isinstance(groupby, list) else [groupby]
    for keys, grp in df.groupby(groupby):
        s = grp[f"{signal_col}_{horizon}"].dropna()
        row = stats_row(s, min_n=min_n)
        if row is None:
            continue
        if not isinstance(keys, tuple):
            keys = (keys,)
        rows.append({
            **{k: v for k, v in zip(group_cols, keys)},
            **{k: row[k] for k in ["n", "hit_rate", "mean_ret", "sharpe", "t_stat", "p_value"]},
        })
    return pd.DataFrame(rows)


def fmt_df(df: pd.DataFrame, cols_pct=None, cols_round=None) -> str:
    """Format a DataFrame as markdown with optional percent/round columns."""
    out = df.copy()
    for col in cols_pct or []:
        if col in out.columns:
            out[col] = (out[col] * 100).round(2).astype(str) + "%"
    for col in cols_round or []:
        if col in out.columns:
            out[col] = out[col].round(3)
    return out.to_markdown(index=False)
