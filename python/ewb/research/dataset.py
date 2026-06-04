"""Dataset row builders for figure research exports."""
from __future__ import annotations

import numpy as np


def figure_rows_from_matches(df, figs, bias, ticker: str, interval: str,
                             horizons=(5, 10, 20, 50, 100),
                             include_w5_ratio: bool = True) -> list[dict]:
    """Build feature rows from matched figures using confirmed entry bars."""
    rows = []
    close = df["close"].to_numpy()
    n = len(close)
    max_horizon = max(horizons)

    for f in figs:
        entry_idx = f.pivots[-1].confirmation_idx
        if entry_idx < 0:
            entry_idx = f.end_idx
        if entry_idx >= n - max_horizon:
            continue
        entry_px = close[entry_idx]
        if entry_px <= 0 or np.isnan(entry_px):
            continue

        bias_val = int(bias.iloc[entry_idx]) if entry_idx < len(bias) else 0
        with_htf = (f.direction == "up" and bias_val > 0) or (
            f.direction == "down" and bias_val < 0
        )
        against_htf = (f.direction == "up" and bias_val < 0) or (
            f.direction == "down" and bias_val > 0
        )

        ws = [abs(f.pivots[i + 1].price - f.pivots[i].price) for i in range(len(f.pivots) - 1)]
        ts = [f.pivots[i + 1].idx - f.pivots[i].idx for i in range(len(f.pivots) - 1)]

        row = {
            "ticker": ticker,
            "interval": interval,
            "end_ts": df.index[f.end_idx],
            "entry_ts": df.index[entry_idx],
            "confirmation_lag": entry_idx - f.end_idx,
            "fig_type": f.type,
            "direction": f.direction,
            "confirmed": f.confirmed,
            "duration": f.duration,
            "amplitude": f.amplitude,
            "amp_pct": f.amplitude / entry_px,
            "htf_bias": bias_val,
            "with_htf": with_htf,
            "against_htf": against_htf,
            "n_pivots": len(f.pivots),
            "n_errors": sum(1 for c in f.checks if c.severity == "E" and not c.ok),
            "n_warnings": sum(1 for c in f.checks if c.severity == "W" and not c.ok),
            "entry_px": entry_px,
            "w1_w2_ratio": (ws[0] / ws[1]) if len(ws) >= 2 and ws[1] > 0 else np.nan,
            "w3_w1_ratio": (ws[2] / ws[0]) if len(ws) >= 3 and ws[0] > 0 else np.nan,
            "w4_w2_ratio": (ws[3] / ws[1]) if len(ws) >= 4 and ws[1] > 0 else np.nan,
            "avg_dur_per_wave": np.mean(ts) if ts else np.nan,
        }
        if include_w5_ratio:
            row["w5_w3_ratio"] = (ws[4] / ws[2]) if len(ws) >= 5 and ws[2] > 0 else np.nan

        for horizon in horizons:
            if entry_idx + horizon < n:
                fut = close[entry_idx + horizon]
                ret = (fut - entry_px) / entry_px
                row[f"ret_{horizon}"] = ret
                sign = -1 if f.direction == "up" else +1
                row[f"signed_ret_{horizon}"] = ret * sign
            else:
                row[f"ret_{horizon}"] = np.nan
                row[f"signed_ret_{horizon}"] = np.nan
        rows.append(row)

    return rows
