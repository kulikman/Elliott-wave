"""Portfolio metrics shared by research scripts."""
from __future__ import annotations

import pandas as pd

from .schema import validate_trade_records


def portfolio_metrics(trades, initial: float = 100_000, risk: float = 0.01,
                      max_conc: int = 10, min_sl_dist: float = 0.005) -> dict | None:
    """Simulate portfolio equity with risk sizing and concurrency cap."""
    if len(trades) == 0:
        return None
    validate_trade_records(trades)
    t = pd.DataFrame(trades)
    t["entry_ts"] = pd.to_datetime(t["entry_ts"], utc=True)
    t["exit_ts"] = pd.to_datetime(t["exit_ts"], utc=True)
    t = t.sort_values("entry_ts").reset_index(drop=True)

    eq = initial
    open_pos, curve = [], []
    skipped = 0
    for _, row in t.iterrows():
        open_pos.sort(key=lambda x: x[0])
        while open_pos and open_pos[0][0] <= row["entry_ts"]:
            ts, pnl = open_pos.pop(0)
            eq += pnl
            curve.append({"ts": ts, "eq": eq})
        if len(open_pos) >= max_conc:
            skipped += 1
            continue
        raw_sl = row["amp_pct"]
        if pd.isna(raw_sl):
            continue
        sl = max(raw_sl, min_sl_dist)
        if sl <= 0:
            continue
        size = min(eq * risk / sl, eq * 0.5)
        open_pos.append((row["exit_ts"], size * row["net_ret"]))
        curve.append({"ts": row["entry_ts"], "eq": eq})

    for ts, pnl in sorted(open_pos):
        eq += pnl
        curve.append({"ts": ts, "eq": eq})
    if not curve:
        return None

    df_eq = pd.DataFrame(curve).sort_values("ts")
    df_eq["ts"] = pd.to_datetime(df_eq["ts"], utc=True)
    equity_curve = df_eq.rename(columns={"eq": "equity"})
    final = df_eq["eq"].iloc[-1]
    peak = df_eq["eq"].cummax()
    dd = (df_eq["eq"] / peak - 1).min()
    daily = df_eq.set_index("ts")["eq"].resample("1D").last().ffill()
    dr = daily.pct_change().dropna()
    yrs = (daily.index[-1] - daily.index[0]).days / 365.25
    cagr = (final / initial) ** (1 / yrs) - 1 if yrs > 0 else 0
    sharpe = dr.mean() / dr.std() * 252 ** 0.5 if dr.std() > 0 else 0
    win_rate = (t["net_ret"] > 0).mean()
    avg_win = t.loc[t["net_ret"] > 0, "net_ret"].mean() * 100 if (t["net_ret"] > 0).any() else 0
    avg_loss = t.loc[t["net_ret"] <= 0, "net_ret"].mean() * 100 if (t["net_ret"] <= 0).any() else 0
    return {
        "n": len(t) - skipped,
        "skipped": skipped,
        "final": final,
        "final_equity": final,
        "total_pct": (final / initial - 1) * 100,
        "total_return": final / initial - 1,
        "cagr": cagr,
        "cagr_pct": cagr * 100,
        "sharpe": sharpe,
        "dd": dd,
        "dd_pct": dd * 100,
        "max_dd": dd * 100,
        "calmar": cagr / abs(dd) if dd != 0 else 0,
        "win": win_rate,
        "win_rate": win_rate * 100,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "yrs": yrs,
        "years": yrs,
        "curve": df_eq,
        "eq_curve": df_eq,
        "equity_curve": equity_curve,
    }
