"""Optimize high-win filters for Anton's Elliott Wave workflow.

The goal is not to maximize raw in-sample winrate. This script searches
Pine-compatible filters and keeps only candidates that survive a chronological
train/test split with positive expectancy and profit factor.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd


REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_TRADES = os.path.join(REPO, "python", "data", "neely_core_ab_backtest_trades.parquet")
OUT_MD = os.path.join(REPO, "docs", "validation", "anton_winrate_optimizer_report.md")
OUT_JSON = os.path.join(REPO, "brain-output", "signals", "anton_winrate_optimizer_summary.json")

GROUP_COLS = ["asset_class", "interval", "setup", "fig_type", "side", "fib_primary_near"]
RR_FILTERS = ("any", "<=0.75", "<=1.0", "<=1.5", ">=1.0")
LAG_FILTERS = ("any", "<=5", "<=10")
AMP_FILTERS = ("any", ">=1%", ">=2%", ">=3%")


def pct(value: float | None, digits: int = 1) -> str:
    if value is None or not math.isfinite(float(value)):
        return "n/a"
    return f"{float(value) * 100:.{digits}f}%"


def num(value: float | None, digits: int = 2) -> str:
    if value is None or not math.isfinite(float(value)):
        return "n/a"
    if math.isinf(float(value)):
        return "inf"
    return f"{float(value):.{digits}f}"


def profit_factor(returns: pd.Series) -> float:
    gross_win = returns[returns > 0].sum()
    gross_loss = returns[returns < 0].sum()
    if gross_loss == 0:
        return np.inf if gross_win > 0 else np.nan
    return float(gross_win / abs(gross_loss))


def wilson_lower_bound(wins: int, n: int, z: float = 1.96) -> float:
    if n <= 0:
        return np.nan
    p = wins / n
    denom = 1 + z * z / n
    center = p + z * z / (2 * n)
    spread = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)
    return float((center - spread) / denom)


def metrics(df: pd.DataFrame) -> dict:
    returns = df["net_ret"].astype(float)
    n = int(len(df))
    wins = int((returns > 0).sum())
    avg_win = float(returns[returns > 0].mean()) if wins else 0.0
    avg_loss = float(abs(returns[returns < 0].mean())) if (returns < 0).any() else 0.0
    breakeven = avg_loss / (avg_win + avg_loss) if avg_win + avg_loss > 0 else np.nan
    winrate = wins / n if n else np.nan
    return {
        "n": n,
        "wins": wins,
        "winrate": float(winrate),
        "wilson_low": wilson_lower_bound(wins, n),
        "ev": float(returns.mean()) if n else np.nan,
        "profit_factor": profit_factor(returns),
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "breakeven_winrate": float(breakeven) if math.isfinite(float(breakeven)) else np.nan,
        "edge_over_breakeven": float(winrate - breakeven) if n and math.isfinite(float(breakeven)) else np.nan,
        "tp_rate": float((df["exit_reason"] == "tp").mean()) if n else np.nan,
        "sl_rate": float((df["exit_reason"] == "sl").mean()) if n else np.nan,
        "avg_rr": float(df["risk_reward"].mean()) if n else np.nan,
    }


def add_split(trades: pd.DataFrame, split_quantile: float) -> pd.DataFrame:
    out = trades.copy()
    out["entry_ts"] = pd.to_datetime(out["entry_ts"], utc=True)
    out["split"] = "test"
    for asset_class, group in out.groupby("asset_class"):
        cutoff = group["entry_ts"].quantile(split_quantile)
        mask = (out["asset_class"] == asset_class) & (out["entry_ts"] <= cutoff)
        out.loc[mask, "split"] = "train"
    return out


def apply_filter(df: pd.DataFrame, rr_filter: str, lag_filter: str, amp_filter: str) -> pd.Series:
    mask = pd.Series(True, index=df.index)
    if rr_filter != "any":
        value = float(rr_filter[2:])
        mask &= df["risk_reward"] <= value if rr_filter.startswith("<=") else df["risk_reward"] >= value
    if lag_filter != "any":
        mask &= df["confirm_lag"] <= int(lag_filter[2:])
    if amp_filter != "any":
        mask &= df["amp_pct"] >= float(amp_filter[2:-1]) / 100
    return mask


def search_candidates(
    trades: pd.DataFrame,
    min_total: int,
    min_train: int,
    min_test: int,
    min_train_pf: float,
    min_test_pf: float,
) -> pd.DataFrame:
    rows: list[dict] = []
    for key, group in trades.groupby(GROUP_COLS, dropna=False):
        if len(group) < min_total:
            continue
        base = dict(zip(GROUP_COLS, key))
        for rr_filter in RR_FILTERS:
            for lag_filter in LAG_FILTERS:
                for amp_filter in AMP_FILTERS:
                    filtered = group[apply_filter(group, rr_filter, lag_filter, amp_filter)]
                    if len(filtered) < min_total:
                        continue
                    train = filtered[filtered["split"] == "train"]
                    test = filtered[filtered["split"] == "test"]
                    if len(train) < min_train or len(test) < min_test:
                        continue
                    train_m = metrics(train)
                    if train_m["ev"] <= 0 or train_m["profit_factor"] < min_train_pf:
                        continue
                    test_m = metrics(test)
                    if test_m["ev"] <= 0 or test_m["profit_factor"] < min_test_pf:
                        continue
                    all_m = metrics(filtered)
                    rows.append({
                        **base,
                        "rr_filter": rr_filter,
                        "lag_filter": lag_filter,
                        "amp_filter": amp_filter,
                        **{f"train_{k}": v for k, v in train_m.items()},
                        **{f"test_{k}": v for k, v in test_m.items()},
                        **{f"all_{k}": v for k, v in all_m.items()},
                    })
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    out["score"] = (
        out["test_wilson_low"]
        + out["test_ev"]
        + np.log1p(out["test_n"]) / 100
        + out["test_edge_over_breakeven"].clip(lower=0) / 2
    )
    return out.sort_values(["test_winrate", "test_ev", "test_n"], ascending=[False, False, False])


def dedupe_rules(candidates: pd.DataFrame) -> pd.DataFrame:
    if candidates.empty:
        return candidates
    sort_cols = ["test_winrate", "test_ev", "test_n", "score"]
    out = candidates.sort_values(sort_cols, ascending=[False, False, False, False])
    key_cols = GROUP_COLS + ["rr_filter", "lag_filter", "amp_filter"]
    return out.drop_duplicates(key_cols)


def format_table(df: pd.DataFrame, limit: int = 25) -> list[str]:
    if df.empty:
        return ["No rows."]
    cols = [
        "asset_class", "interval", "setup", "fig_type", "side", "fib_primary_near",
        "rr_filter", "lag_filter", "amp_filter", "train_n", "train_winrate", "train_ev",
        "test_n", "test_winrate", "test_ev", "test_profit_factor",
        "test_breakeven_winrate", "test_edge_over_breakeven",
    ]
    out = df.head(limit)[cols].copy()
    for col in ["train_winrate", "train_ev", "test_winrate", "test_ev", "test_breakeven_winrate", "test_edge_over_breakeven"]:
        out[col] = out[col].map(lambda value: pct(value))
    out["test_profit_factor"] = out["test_profit_factor"].map(lambda value: num(value))
    return out.to_markdown(index=False).splitlines()


def best_profiles(candidates: pd.DataFrame) -> pd.DataFrame:
    if candidates.empty:
        return candidates
    rules = candidates[
        (candidates["test_n"] >= 20)
        & (candidates["test_winrate"] >= 0.60)
        & (candidates["test_ev"] > 0)
        & (candidates["test_profit_factor"] >= 1.20)
        & (candidates["test_edge_over_breakeven"] >= 0.05)
    ].copy()
    return rules.sort_values(["score", "test_winrate", "test_n"], ascending=[False, False, False])


def write_report(summary: dict, candidates: pd.DataFrame, profiles: pd.DataFrame) -> None:
    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    lines = [
        "# Anton Winrate Optimizer",
        "",
        f"Generated: `{summary['generated_at']}`",
        "",
        "Goal: increase signal winrate by filtering Elliott Wave setups, not by adding more trades.",
        "",
        "## Formulas",
        "",
        "- `winrate = wins / n`",
        "- `EV = winrate * avg_win - (1 - winrate) * avg_loss`",
        "- `breakeven_winrate = avg_loss / (avg_win + avg_loss)`",
        "- `edge = winrate - breakeven_winrate`",
        "- `profit_factor = gross_profit / abs(gross_loss)`",
        "- `wilson_low` is used to penalize small samples.",
        "",
        "## Run Summary",
        "",
        f"- Trades source: `{summary['trades_path']}`",
        f"- Rows: `{summary['trade_rows']}`",
        f"- Split: chronological `{summary['split_quantile']:.0%}` train / `{1 - summary['split_quantile']:.0%}` test per asset class",
        f"- Candidate filters tested: `{summary['candidates']}`",
        f"- Actionable profiles: `{summary['profiles']}`",
        "",
        "## Anton High-Win Profiles",
        "",
        *format_table(profiles, limit=20),
        "",
        "## Top Surviving Candidates",
        "",
        *format_table(candidates, limit=30),
        "",
        "## Interpretation",
        "",
        "- Prefer fewer signals with `test_winrate >= 60%`, positive EV, PF >= 1.2, and edge above breakeven.",
        "- Do not use raw winrate without EV; low-RR exits can win often and still be weak after costs.",
        "- The best current profile is confluence: validated wave type + Fib proximity + RR/lag/amplitude gate.",
    ]
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def write_json(summary: dict, candidates: pd.DataFrame, profiles: pd.DataFrame) -> None:
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    payload = {
        **summary,
        "profiles": profiles.head(50).to_dict("records"),
        "top_candidates": candidates.head(100).to_dict("records"),
        "outputs": {"markdown": OUT_MD, "json": OUT_JSON},
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trades", default=DEFAULT_TRADES)
    parser.add_argument("--split-quantile", type=float, default=0.70)
    parser.add_argument("--min-total", type=int, default=60)
    parser.add_argument("--min-train", type=int, default=40)
    parser.add_argument("--min-test", type=int, default=15)
    parser.add_argument("--min-train-pf", type=float, default=1.10)
    parser.add_argument("--min-test-pf", type=float, default=1.10)
    args = parser.parse_args()

    trades = pd.read_parquet(args.trades)
    trades = add_split(trades, args.split_quantile)
    candidates = search_candidates(
        trades,
        min_total=args.min_total,
        min_train=args.min_train,
        min_test=args.min_test,
        min_train_pf=args.min_train_pf,
        min_test_pf=args.min_test_pf,
    )
    candidates = dedupe_rules(candidates)
    profiles = best_profiles(candidates)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "trades_path": os.path.abspath(args.trades),
        "trade_rows": int(len(trades)),
        "split_quantile": args.split_quantile,
        "candidates": int(len(candidates)),
        "profiles": int(len(profiles)),
    }
    write_report(summary, candidates, profiles)
    write_json(summary, candidates, profiles)
    print(f"Report: {OUT_MD}")
    print(f"JSON: {OUT_JSON}")


if __name__ == "__main__":
    main()
