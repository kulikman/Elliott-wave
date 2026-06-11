"""A/B backtest for book-derived Neely Core signals.

This script compares the current baseline figure trades with new research
signals derived from the collected Neely rules:
- impulse post-pattern pullback;
- triangle thrust;
- zigzag C=A / 161.8 context;
- moving correction follow-through;
- Fibonacci ratio buckets for wave/figure probability checks.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import warnings
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

import scripts.historical_signal_grid as hgrid
from ewb.figures import Figure, match_figures
from ewb.monowaves import detect_monowaves
from ewb.research import cost_for
from ewb.rules import classify_pivots


REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_MD = os.path.join(REPO, "docs", "validation", "neely_core_ab_backtest_report.md")
OUT_JSON = os.path.join(REPO, "brain-output", "signals", "neely_core_ab_backtest_summary.json")
OUT_TRADES = os.path.join(REPO, "python", "data", "neely_core_ab_backtest_trades.parquet")
OHLC_CACHE_DIR = os.path.join(REPO, "python", "data", "ohlc_cache")

TOP20_STOCKS = hgrid.TOP100_STOCKS[:20]
TOP20_CRYPTO = hgrid.CRYPTO_UNIVERSE[:20]
INTERVALS = tuple(hgrid.INTERVALS.keys())
FIBS = (0.236, 0.382, 0.5, 0.618, 0.786, 1.0, 1.272, 1.382, 1.618, 2.0, 2.618)
EXIT_BARS = {
    "flat": 20,
    "double_corr": 50,
    "impulse": 50,
    "triangle": 30,
    "zigzag": 30,
    "moving_corr": 50,
}


def normalize_utc_index(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    idx = pd.to_datetime(out.index)
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    else:
        idx = idx.tz_convert("UTC")
    out.index = idx
    return out


def stock_cache_path(ticker: str, label: str, period: str) -> str:
    safe_ticker = ticker.replace("/", "-").replace(".", "-").replace(" ", "-")
    return os.path.join(OHLC_CACHE_DIR, "tiingo", f"{safe_ticker}_{label}_{period}.parquet")


def read_stock_cache(ticker: str, label: str, period: str) -> pd.DataFrame | None:
    path = stock_cache_path(ticker, label, period)
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_parquet(path)
    except Exception:
        return None
    if "date" in df.columns:
        df = df.set_index("date")
    base_cols = {"open", "high", "low", "close"}
    if df.empty or not base_cols.issubset(df.columns):
        return None
    return normalize_utc_index(df.sort_index())


def side_int(side: str) -> int:
    return 1 if side == "long" else -1


def pct(value: float | None, digits: int = 1) -> str:
    if value is None or not math.isfinite(float(value)):
        return "n/a"
    return f"{float(value) * 100:.{digits}f}%"


def num(value: float | None, digits: int = 2) -> str:
    if value is None or not math.isfinite(float(value)):
        return "n/a"
    return f"{float(value):.{digits}f}"


def nearest_fib(value: float | None, tolerance: float = 0.10) -> tuple[str, bool]:
    if value is None or not math.isfinite(float(value)) or value <= 0:
        return "n/a", False
    best = min(FIBS, key=lambda fib: abs(float(value) - fib))
    near = abs(float(value) - best) <= best * tolerance
    label = f"{best:g}" if near else "off"
    return label, near


def wave_lengths(fig: Figure) -> list[float]:
    return [
        abs(fig.pivots[i + 1].price - fig.pivots[i].price)
        for i in range(len(fig.pivots) - 1)
    ]


def ratio(numer: float, denom: float) -> float:
    return float(numer / denom) if denom and denom > 0 else np.nan


def fib_features(fig: Figure) -> dict:
    ws = wave_lengths(fig)
    out: dict[str, float | str | bool] = {
        "fib_primary_ratio": np.nan,
        "fib_primary_bucket": "n/a",
        "fib_primary_near": False,
        "fib_b_a": np.nan,
        "fib_c_a": np.nan,
        "fib_w3_w1": np.nan,
        "fib_w5_w1": np.nan,
    }
    if fig.type in {"flat", "zigzag", "double_corr"} and len(ws) >= 3:
        out["fib_b_a"] = ratio(ws[1], ws[0])
        out["fib_c_a"] = ratio(ws[2], ws[0])
        primary = out["fib_c_a"] if fig.type != "double_corr" else out["fib_b_a"]
    elif fig.type in {"impulse", "triangle"} and len(ws) >= 5:
        out["fib_w3_w1"] = ratio(ws[2], ws[0])
        out["fib_w5_w1"] = ratio(ws[4], ws[0])
        primary = out["fib_w3_w1"] if fig.type == "impulse" else ratio(ws[2], ws[0])
    else:
        primary = np.nan
    bucket, near = nearest_fib(primary)
    out["fib_primary_ratio"] = primary
    out["fib_primary_bucket"] = bucket
    out["fib_primary_near"] = near
    return out


def entry_index(fig: Figure) -> int:
    idx = fig.pivots[-1].confirmation_idx if fig.pivots else -1
    return idx if idx >= 0 else fig.end_idx


def simulate_level_exit(
    df: pd.DataFrame,
    entry_idx: int,
    side: str,
    target: float,
    stop: float,
    exit_bars: int,
    cost: float,
    entry_px_override: float | None = None,
) -> dict | None:
    if entry_idx < 0 or entry_idx + 1 >= len(df):
        return None
    # next_open execution: pass entry_idx = confirmation bar and override the
    # fill with the NEXT bar's open. Replay then starts at entry_idx+1 (the
    # entry bar), so its range can trigger SL/TP right after the open fill.
    entry_px = (float(entry_px_override) if entry_px_override is not None
                else float(df["close"].iloc[entry_idx]))
    if entry_px <= 0 or not math.isfinite(target) or not math.isfinite(stop):
        return None
    sign = side_int(side)
    reward = sign * (target - entry_px)
    risk = sign * (entry_px - stop)
    if reward <= 0 or risk <= 0:
        return None
    high = df["high"].to_numpy(float)
    low = df["low"].to_numpy(float)
    close = df["close"].to_numpy(float)
    last_idx = min(entry_idx + exit_bars, len(df) - 1)
    exit_idx = last_idx
    exit_px = float(close[last_idx])
    reason = "time"
    for i in range(entry_idx + 1, last_idx + 1):
        if side == "long":
            if low[i] <= stop:
                exit_idx, exit_px, reason = i, stop, "sl"
                break
            if high[i] >= target:
                exit_idx, exit_px, reason = i, target, "tp"
                break
        else:
            if high[i] >= stop:
                exit_idx, exit_px, reason = i, stop, "sl"
                break
            if low[i] <= target:
                exit_idx, exit_px, reason = i, target, "tp"
                break
    raw_ret = sign * (exit_px - entry_px) / entry_px
    net_ret = raw_ret - 2 * cost
    return {
        "entry_px": entry_px,
        "target_px": float(target),
        "stop_px": float(stop),
        "risk_reward": float(reward / risk),
        "exit_idx": int(exit_idx),
        "exit_ts": df.index[exit_idx],
        "exit_px": float(exit_px),
        "bars_held": int(exit_idx - entry_idx),
        "raw_ret": float(raw_ret),
        "net_ret": float(net_ret),
        "win": bool(net_ret > 0),
        "exit_reason": reason,
    }


def simulate_amp_exit(
    df: pd.DataFrame,
    entry_idx: int,
    side: str,
    amp: float,
    exit_bars: int,
    cost: float,
    tp_mult: float = 1.0,
    sl_mult: float = 1.0,
) -> dict | None:
    if entry_idx < 0 or entry_idx >= len(df):
        return None
    entry_px = float(df["close"].iloc[entry_idx])
    sign = side_int(side)
    target = entry_px + sign * amp * tp_mult
    stop = entry_px - sign * amp * sl_mult
    return simulate_level_exit(df, entry_idx, side, target, stop, exit_bars, cost)


def baseline_setups(fig: Figure) -> list[dict]:
    if fig.type == "flat":
        side = "short" if fig.direction == "up" else "long"
        return [{"ab_group": "A", "setup": "baseline_flat_fade", "side": side}]
    if fig.type == "double_corr":
        side = "short" if fig.direction == "up" else "long"
        return [{"ab_group": "A", "setup": "baseline_double_corr_fade", "side": side}]
    return []


def neely_core_setups(fig: Figure) -> list[dict]:
    p = [pivot.price for pivot in fig.pivots]
    ws = wave_lengths(fig)
    out: list[dict] = []
    if fig.type == "impulse" and len(p) >= 6:
        side = "short" if fig.direction == "up" else "long"
        amp = abs(p[-1] - p[0])
        target = p[4]
        stop = p[-1] + (1 if fig.direction == "up" else -1) * amp * 0.382
        out.append({
            "ab_group": "B",
            "setup": "core_impulse_post_w4",
            "side": side,
            "target": target,
            "stop": stop,
            "book_rule": "post-pattern impulse: pullback toward W4",
        })
    elif fig.type == "triangle" and len(p) >= 6 and len(ws) >= 5:
        e_dir = 1 if p[5] > p[4] else -1
        thrust_dir = -e_dir
        widest = max(ws[:5])
        side = "long" if thrust_dir > 0 else "short"
        out.append({
            "ab_group": "B",
            "setup": "core_triangle_thrust",
            "side": side,
            "target": p[5] + thrust_dir * widest,
            "stop": p[5] - thrust_dir * widest * 0.382,
            "book_rule": "post-pattern triangle thrust",
        })
    elif fig.type == "zigzag" and len(p) >= 4 and len(ws) >= 3:
        a = ws[0]
        c_target_100 = p[2] + (1 if fig.direction == "up" else -1) * a
        c_target_161 = p[2] + (1 if fig.direction == "up" else -1) * a * 1.618
        c_at_one = abs(p[3] - c_target_100) <= a * 0.10
        if c_at_one:
            side = "short" if fig.direction == "up" else "long"
            out.append({
                "ab_group": "B",
                "setup": "core_zigzag_reversal_c_eq_a",
                "side": side,
                "target": p[2],
                "stop": c_target_161,
                "book_rule": "zigzag C approximately equals A",
            })
        else:
            side = "long" if fig.direction == "up" else "short"
            out.append({
                "ab_group": "B",
                "setup": "core_zigzag_follow_to_c_eq_a",
                "side": side,
                "target": c_target_100,
                "stop": p[2],
                "book_rule": "zigzag C=A completion watch",
            })
    elif fig.type == "flat" and len(p) >= 4 and len(ws) >= 3:
        a, b, c = ws[:3]
        b_beyond_start = p[2] < p[0] if fig.direction == "up" else p[2] > p[0]
        c_fails_a_end = p[3] < p[1] if fig.direction == "up" else p[3] > p[1]
        if a > 0 and b / a >= 1.0 and c / a >= 0.618 and b_beyond_start and c_fails_a_end:
            trend_dir = -1 if fig.direction == "up" else 1
            side = "long" if trend_dir > 0 else "short"
            out.append({
                "ab_group": "B",
                "setup": "core_moving_correction_follow",
                "side": side,
                "target_offset": a * 1.618 * trend_dir,
                "stop_offset": -a * 0.382 * trend_dir,
                "book_rule": "moving correction: expect strong impulse",
            })
    return out


def build_rows_for_frame(
    ticker: str,
    asset_class: str,
    interval: str,
    df: pd.DataFrame,
    universe_rank: int,
) -> list[dict]:
    pivots = detect_monowaves(df, atr_mult=2.5)
    classify_pivots(pivots)
    figures = [fig for fig in match_figures(pivots) if fig.confirmed and fig.pivots]
    cost = cost_for(ticker)
    rows: list[dict] = []
    for fig in figures:
        eidx = entry_index(fig)
        if eidx < 0 or eidx >= len(df) - 2 or fig.amplitude <= 0:
            continue
        feature = fib_features(fig)
        setups = baseline_setups(fig) + neely_core_setups(fig)
        for setup in setups:
            side = setup["side"]
            if "target" in setup and "stop" in setup:
                result = simulate_level_exit(
                    df, eidx, side, float(setup["target"]), float(setup["stop"]),
                    EXIT_BARS.get(fig.type, 30), cost,
                )
            else:
                entry_px = float(df["close"].iloc[eidx])
                target = entry_px + float(setup.get("target_offset", 0))
                stop = entry_px + float(setup.get("stop_offset", 0))
                result = (
                    simulate_level_exit(df, eidx, side, target, stop, EXIT_BARS.get("moving_corr", 50), cost)
                    if "target_offset" in setup
                    else simulate_amp_exit(df, eidx, side, fig.amplitude, EXIT_BARS.get(fig.type, 30), cost)
                )
            if result is None:
                continue
            rows.append({
                "ticker": ticker,
                "asset_class": asset_class,
                "universe_rank": universe_rank,
                "interval": interval,
                "ab_group": setup["ab_group"],
                "setup": setup["setup"],
                "fig_type": "moving_corr" if setup["setup"] == "core_moving_correction_follow" else fig.type,
                "direction": fig.direction,
                "side": side,
                "entry_idx": int(eidx),
                "entry_ts": df.index[eidx],
                "pattern_start_idx": int(fig.start_idx),
                "pattern_end_idx": int(fig.end_idx),
                "confirm_lag": int(eidx - fig.end_idx),
                "amplitude": float(fig.amplitude),
                "amp_pct": float(fig.amplitude / max(result["entry_px"], 1e-12)),
                "duration": int(fig.duration),
                "book_rule": setup.get("book_rule", "baseline current figure fade"),
                **feature,
                **result,
            })
    return rows


def load_asset_frame(
    ticker: str,
    asset_class: str,
    interval: str,
    cache_1h: dict[str, pd.DataFrame | None],
    stock_provider: str,
) -> pd.DataFrame | None:
    hgrid.ACTIVE_ASSET_CLASS = asset_class
    hgrid.ACTIVE_UNIVERSE = TOP20_CRYPTO if asset_class == "crypto" else hgrid.TOP100_STOCKS
    if asset_class == "stocks" and stock_provider in {"auto", "tiingo-cache"}:
        cfg = hgrid.INTERVALS[interval]
        if cfg["source"] == "resample_4h":
            raw = cache_1h.get(ticker)
            if raw is None:
                raw = read_stock_cache(ticker, "1h", "730d")
                cache_1h[ticker] = raw
            cached = hgrid.resample_ohlc(raw, "4h") if raw is not None else None
        else:
            cached = read_stock_cache(ticker, interval, cfg["period"])
            if interval == "1h":
                cache_1h[ticker] = cached
        if cached is not None:
            return cached
        if stock_provider == "tiingo-cache":
            return None
    return hgrid.load_frame(ticker, interval, cache_1h)


def profit_factor(series: pd.Series) -> float:
    wins = series[series > 0].sum()
    losses = series[series < 0].sum()
    if losses == 0:
        return np.inf if wins > 0 else np.nan
    return float(wins / abs(losses))


def max_drawdown(series: pd.Series) -> float:
    if series.empty:
        return np.nan
    eq = (1 + series).cumprod()
    return float((eq / eq.cummax() - 1).min())


def metric_row(df: pd.DataFrame) -> dict:
    ret = df["net_ret"].astype(float)
    return {
        "n": int(len(df)),
        "winrate": float((ret > 0).mean()),
        "ev": float(ret.mean()),
        "median": float(ret.median()),
        "profit_factor": profit_factor(ret),
        "max_drawdown": max_drawdown(ret),
        "tp_rate": float((df["exit_reason"] == "tp").mean()),
        "sl_rate": float((df["exit_reason"] == "sl").mean()),
        "avg_rr": float(df["risk_reward"].mean()),
    }


def aggregate(trades: pd.DataFrame, min_n: int = 5) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = []
    group_cols = ["asset_class", "interval", "ab_group", "setup", "fig_type", "side"]
    for key, grp in trades.groupby(group_cols, dropna=False):
        if len(grp) < min_n:
            continue
        row = dict(zip(group_cols, key))
        row.update(metric_row(grp))
        rows.append(row)
    setup_df = pd.DataFrame(rows).sort_values(["asset_class", "ev", "winrate"], ascending=[True, False, False])

    fib_rows = []
    fib_cols = ["asset_class", "interval", "setup", "fig_type", "fib_primary_bucket", "fib_primary_near"]
    for key, grp in trades.groupby(fib_cols, dropna=False):
        if len(grp) < min_n:
            continue
        row = dict(zip(fib_cols, key))
        row.update(metric_row(grp))
        fib_rows.append(row)
    fib_df = pd.DataFrame(fib_rows).sort_values(["asset_class", "ev", "winrate"], ascending=[True, False, False])

    wave_rows = []
    wave_cols = ["asset_class", "interval", "fig_type", "direction"]
    for key, grp in trades.groupby(wave_cols, dropna=False):
        if len(grp) < min_n:
            continue
        row = dict(zip(wave_cols, key))
        row.update(metric_row(grp))
        wave_rows.append(row)
    wave_df = pd.DataFrame(wave_rows).sort_values(["asset_class", "ev", "winrate"], ascending=[True, False, False])
    return setup_df, fib_df, wave_df


def markdown_table(df: pd.DataFrame, cols: list[str], limit: int = 20) -> list[str]:
    if df.empty:
        return ["No rows."]
    out = df.head(limit).copy()
    for col in ["winrate", "ev", "median", "max_drawdown", "tp_rate", "sl_rate"]:
        if col in out:
            out[col] = out[col].map(lambda v: pct(v, 2 if col in {"ev", "median"} else 1))
    for col in ["profit_factor", "avg_rr"]:
        if col in out:
            out[col] = out[col].map(lambda v: num(v, 2))
    return out[cols].to_markdown(index=False).splitlines()


def coverage_table(summary: dict) -> list[str]:
    coverage = summary.get("coverage", [])
    if not coverage:
        return ["No coverage rows."]
    df = pd.DataFrame(coverage)
    rows = []
    for key, grp in df.groupby(["asset_class", "interval"]):
        row = {
            "asset_class": key[0],
            "interval": key[1],
            "requested": int(len(grp)),
            "ok": int(grp["ok"].sum()),
            "missing": int((~grp["ok"]).sum()),
            "trades": int(grp["trade_rows"].sum()),
        }
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["asset_class", "interval"]).to_markdown(index=False).splitlines()


def write_report(summary: dict, setup_df: pd.DataFrame, fib_df: pd.DataFrame, wave_df: pd.DataFrame) -> None:
    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    setup_cols = ["asset_class", "interval", "ab_group", "setup", "fig_type", "side", "n", "winrate", "ev", "profit_factor", "max_drawdown", "tp_rate", "sl_rate"]
    fib_cols = ["asset_class", "interval", "setup", "fig_type", "fib_primary_bucket", "fib_primary_near", "n", "winrate", "ev", "profit_factor"]
    wave_cols = ["asset_class", "interval", "fig_type", "direction", "n", "winrate", "ev", "profit_factor", "max_drawdown"]
    lines = [
        "# Neely Core A/B Backtest",
        "",
        f"Generated: `{summary['generated_at']}`",
        "",
        "Scope: top20 stocks and top20 crypto. Baseline A = current flat/double_corr fade. Core B = book-derived Neely signals with Fibonacci buckets.",
        "",
        "## Run Summary",
        "",
        f"- Assets: `{', '.join(summary['asset_classes'])}`",
        f"- Intervals: `{', '.join(summary['intervals'])}`",
        f"- Usable frames: `{summary['frames_ok']}` / `{summary['frames_requested']}`",
        f"- Trade rows: `{summary['trade_rows']}`",
        f"- Stock provider: `{summary.get('stock_provider', 'n/a')}`",
        f"- Output trades: `{OUT_TRADES}`",
        "",
        "## Data Coverage",
        "",
        *coverage_table(summary),
        "",
        "## A/B Setup Results",
        "",
        *markdown_table(setup_df, setup_cols, limit=30),
        "",
        "## Fibonacci Probability Buckets",
        "",
        *markdown_table(fib_df, fib_cols, limit=30),
        "",
        "## Wave/Figure Probability",
        "",
        *markdown_table(wave_df, wave_cols, limit=30),
        "",
        "## Interpretation Rules",
        "",
        "- Do not promote a Core B signal to BUY/SELL unless it has positive EV, acceptable PF, and enough sample size out-of-sample in the next grid.",
        "- Fibonacci buckets with `fib_primary_near=True` show whether classic ratios improved the setup probability.",
        "- Crypto remains research-only unless its rows are stable separately from stock rows.",
    ]
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def write_outputs(trades: pd.DataFrame, setup_df: pd.DataFrame, fib_df: pd.DataFrame, wave_df: pd.DataFrame, summary: dict) -> None:
    os.makedirs(os.path.dirname(OUT_TRADES), exist_ok=True)
    trades.to_parquet(OUT_TRADES, index=False)
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    payload = {
        **summary,
        "best_setups": setup_df.head(50).to_dict("records"),
        "best_fib_buckets": fib_df.head(50).to_dict("records"),
        "best_wave_figures": wave_df.head(50).to_dict("records"),
        "outputs": {"markdown": OUT_MD, "json": OUT_JSON, "trades": OUT_TRADES},
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    write_report(summary, setup_df, fib_df, wave_df)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset-class", choices=["stocks", "crypto", "both"], default="both")
    parser.add_argument("--intervals", nargs="*", default=list(INTERVALS))
    parser.add_argument("--stock-provider", choices=["auto", "tiingo-cache", "yfinance"], default="auto")
    parser.add_argument("--from-trades", action="store_true")
    args = parser.parse_args()

    if args.from_trades:
        trades = pd.read_parquet(OUT_TRADES)
        setup_df, fib_df, wave_df = aggregate(trades)
        summary = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "asset_classes": sorted(trades["asset_class"].unique()),
            "intervals": args.intervals,
            "frames_requested": 0,
            "frames_ok": int(trades[["ticker", "interval"]].drop_duplicates().shape[0]),
            "trade_rows": int(len(trades)),
            "failures": [],
            "coverage": [],
            "stock_provider": args.stock_provider,
        }
        write_outputs(trades, setup_df, fib_df, wave_df, summary)
        return

    asset_classes = ["stocks", "crypto"] if args.asset_class == "both" else [args.asset_class]
    rows: list[dict] = []
    failures: list[dict] = []
    coverage: list[dict] = []
    frames_ok = 0
    frames_requested = 0
    for asset_class in asset_classes:
        tickers = TOP20_STOCKS if asset_class == "stocks" else TOP20_CRYPTO
        cache_1h: dict[str, pd.DataFrame | None] = {}
        for rank, ticker in enumerate(tickers, start=1):
            for interval in args.intervals:
                frames_requested += 1
                try:
                    df = load_asset_frame(ticker, asset_class, interval, cache_1h, args.stock_provider)
                    if df is None or len(df) < 100:
                        failures.append({"ticker": ticker, "asset_class": asset_class, "interval": interval, "error": "not_enough_data"})
                        coverage.append({
                            "ticker": ticker,
                            "asset_class": asset_class,
                            "interval": interval,
                            "ok": False,
                            "bars": 0 if df is None else int(len(df)),
                            "trade_rows": 0,
                        })
                        continue
                    frame_rows = build_rows_for_frame(ticker, asset_class, interval, df, rank)
                    rows.extend(frame_rows)
                    frames_ok += 1
                    coverage.append({
                        "ticker": ticker,
                        "asset_class": asset_class,
                        "interval": interval,
                        "ok": True,
                        "bars": int(len(df)),
                        "trade_rows": int(len(frame_rows)),
                    })
                    print(f"[{asset_class}] {ticker:10} {interval:3} rows={len(frame_rows):5} total={len(rows):7}", flush=True)
                except Exception as exc:
                    failures.append({"ticker": ticker, "asset_class": asset_class, "interval": interval, "error": repr(exc)})
                    coverage.append({
                        "ticker": ticker,
                        "asset_class": asset_class,
                        "interval": interval,
                        "ok": False,
                        "bars": 0,
                        "trade_rows": 0,
                    })
                    print(f"[{asset_class}] {ticker:10} {interval:3} ERROR {exc!r}", flush=True)
    if not rows:
        raise SystemExit("No backtest rows generated.")
    trades = pd.DataFrame(rows)
    trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
    trades["exit_ts"] = pd.to_datetime(trades["exit_ts"], utc=True)
    setup_df, fib_df, wave_df = aggregate(trades)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "asset_classes": asset_classes,
        "intervals": args.intervals,
        "frames_requested": frames_requested,
        "frames_ok": frames_ok,
        "trade_rows": int(len(trades)),
        "failures": failures[:200],
        "coverage": coverage,
        "stock_provider": args.stock_provider,
    }
    write_outputs(trades, setup_df, fib_df, wave_df, summary)
    print(f"Report: {OUT_MD}")
    print(f"Trades: {OUT_TRADES}")


if __name__ == "__main__":
    main()
