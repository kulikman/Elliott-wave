"""Build an EWB bot-readiness backtest report from historical trade grids."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ewb.strategy_system import (
    DEFAULT_BACKTEST_DIR,
    StrategyContract,
    contract_payload,
    filter_contract_trades,
    grouped_summary,
    markdown_table,
    normalize_historical_trades,
    trade_summary,
    walk_forward_summary,
    write_frame,
    write_json,
)


REPO = Path(__file__).resolve().parents[2]
DEFAULT_STOCK_TRADES = REPO / "python/data/historical_signal_grid_trades.parquet"
DEFAULT_CRYPTO_TRADES = REPO / "python/data/historical_signal_grid_crypto_trades.parquet"


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--stock-trades", default=str(DEFAULT_STOCK_TRADES))
    p.add_argument("--crypto-trades", default=str(DEFAULT_CRYPTO_TRADES))
    p.add_argument("--asset-class", choices=["stocks", "crypto", "both"], default="both")
    p.add_argument("--intervals", nargs="*", default=["1h", "4h", "1d", "1w"])
    p.add_argument("--universe-limit", type=int, default=100)
    p.add_argument("--min-model-p", type=float, default=55.0)
    p.add_argument("--min-sample", type=int, default=20)
    p.add_argument("--entry-variants", nargs="*", default=["confirm_close"])
    p.add_argument("--mtf-policies", nargs="*", default=["none"])
    p.add_argument("--late-limit", type=float, default=999.0)
    p.add_argument("--tp-mult", type=float, default=1.0)
    p.add_argument("--sl-mult", type=float, default=1.0)
    p.add_argument("--exit-plan", default="full")
    p.add_argument("--folds", type=int, default=6)
    p.add_argument("--output-dir", default=str(REPO / DEFAULT_BACKTEST_DIR))
    return p


def load_trade_file(path: Path, asset_class: str) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return normalize_historical_trades(pd.read_parquet(path), asset_class=asset_class)


def load_scope(args: argparse.Namespace) -> pd.DataFrame:
    frames = []
    if args.asset_class in {"stocks", "both"}:
        frames.append(load_trade_file(Path(args.stock_trades), "stock"))
    if args.asset_class in {"crypto", "both"}:
        frames.append(load_trade_file(Path(args.crypto_trades), "crypto"))
    frames = [df for df in frames if not df.empty]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def write_markdown(
    path: Path,
    *,
    summary: dict,
    grouped: pd.DataFrame,
    by_setup: pd.DataFrame,
    walk_forward: pd.DataFrame,
    args: argparse.Namespace,
) -> None:
    columns = [
        ("Asset", "asset_class"), ("TF", "interval"), ("Pattern", "fig_type"),
        ("Side", "side"), ("Trades", "trades"), ("Win", "winrate"),
        ("Exp", "expectancy"), ("PF", "profit_factor"), ("DD", "max_drawdown"),
    ]
    setup_cols = [
        ("Setup", "setup_key"), ("Trades", "trades"), ("Win", "winrate"),
        ("Exp", "expectancy"), ("PF", "profit_factor"), ("DD", "max_drawdown"),
    ]
    wf_cols = [
        ("Fold", "fold"), ("Start", "start"), ("End", "end"), ("Trades", "trades"),
        ("Win", "winrate"), ("Exp", "expectancy"), ("PF", "profit_factor"), ("DD", "max_drawdown"),
    ]
    lines = [
        "# EWB Strategy System Backtest",
        "",
        "This report tests the bot contract around the TradingView indicator. Pine remains the visual/alert surface; this report is the statistical control surface.",
        "",
        "## Contract",
        "",
        f"- Strategy: `{summary['contract']['strategy_id']}`",
        f"- Entry rule: `{summary['contract']['entry_rule']}`",
        f"- Exit rule: `{summary['contract']['exit_rule']}`",
        f"- Patterns: `{', '.join(summary['contract']['allowed_patterns'])}`",
        f"- Intervals: `{', '.join(args.intervals)}`",
        f"- Filters: min model P `{args.min_model_p}%`, min sample `{args.min_sample}`, universe rank <= `{args.universe_limit}`",
        f"- Canonical slice: entry `{', '.join(args.entry_variants)}`, MTF `{', '.join(args.mtf_policies)}`, late `{args.late_limit}`, TP `{args.tp_mult}`, SL `{args.sl_mult}`, exit `{args.exit_plan}`",
        "",
        "## Portfolio Summary",
        "",
        markdown_table([summary["portfolio"]], [
            ("Trades", "trades"), ("Win", "winrate"), ("Exp", "expectancy"),
            ("PF", "profit_factor"), ("DD", "max_drawdown"), ("Total", "total_return"),
        ], limit=1),
        "",
        "## By Asset / TF / Pattern",
        "",
        markdown_table(grouped.to_dict("records"), columns, limit=30),
        "",
        "## Best Setup Keys",
        "",
        markdown_table(by_setup.to_dict("records"), setup_cols, limit=30),
        "",
        "## Walk Forward Folds",
        "",
        markdown_table(walk_forward.to_dict("records"), wf_cols, limit=20),
        "",
        "## How To Use",
        "",
        "- Use this as the historical baseline before turning on a bot.",
        "- Then run `forward_signal_logger.py add` for every alert and `settle` for every exit.",
        "- Compare live forward trades with this baseline using `compare_backtest_forward.py`.",
        "- Do not optimize against the forward log; it is the reality check.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parser().parse_args()
    output_dir = Path(args.output_dir)
    contract = StrategyContract()
    raw = load_scope(args)
    scoped = filter_contract_trades(
        raw,
        contract=contract,
        min_model_p=args.min_model_p,
        min_sample=args.min_sample,
        intervals=set(args.intervals),
        universe_limit=args.universe_limit,
        entry_variants=set(args.entry_variants),
        mtf_policies=set(args.mtf_policies),
        late_limit=args.late_limit,
        tp_mult=args.tp_mult,
        sl_mult=args.sl_mult,
        exit_plan=args.exit_plan,
    )
    scoped = scoped.sort_values("entry_ts") if not scoped.empty else scoped
    keys = ["asset_class", "interval", "fig_type", "side"]
    grouped = grouped_summary(scoped, keys)            # in-sample, for the markdown report
    by_setup = grouped_summary(scoped, ["setup_key"])
    walk_forward = walk_forward_summary(scoped, folds=args.folds)
    portfolio = trade_summary(scoped)

    # Gate LUT = out-of-sample + stability (same as W3/core): chronological
    # 70/30 split; keep only setups whose expectancy is positive in BOTH the
    # train and held-out test slices, carrying the OOS (test) metrics.
    gate_lut = grouped
    if not scoped.empty and "entry_ts" in scoped.columns:
        sc = scoped.assign(_ts=pd.to_datetime(scoped["entry_ts"], utc=True, errors="coerce"))
        sc = sc.dropna(subset=["_ts"]).sort_values("_ts")
        if len(sc) >= 20:
            cut = sc["_ts"].quantile(0.70)
            g_tr = grouped_summary(sc[sc["_ts"] <= cut], keys)
            g_te = grouped_summary(sc[sc["_ts"] > cut], keys)
            if not g_tr.empty and not g_te.empty:
                tr_pos = {tuple(r[k] for k in keys) for _, r in g_tr.iterrows() if r["expectancy"] > 0}
                gate_lut = g_te[
                    g_te.apply(lambda r: r["expectancy"] > 0
                               and tuple(r[k] for k in keys) in tr_pos, axis=1)
                ].copy()

    trades_path = write_frame(scoped, output_dir / "ewb_strategy_backtest_trades.parquet")
    grouped_path = write_frame(gate_lut, output_dir / "ewb_strategy_backtest_grouped.parquet")
    wf_path = write_frame(walk_forward, output_dir / "ewb_strategy_walk_forward.parquet")
    summary = {
        "contract": contract_payload(contract),
        "raw_rows": int(len(raw)),
        "scoped_rows": int(len(scoped)),
        "portfolio": portfolio,
        "outputs": {
            "trades": str(trades_path),
            "grouped": str(grouped_path),
            "walk_forward": str(wf_path),
            "markdown": str(output_dir / "ewb_strategy_backtest.md"),
            "json": str(output_dir / "ewb_strategy_backtest_summary.json"),
        },
    }
    write_json(output_dir / "ewb_strategy_backtest_summary.json", summary)
    write_markdown(
        output_dir / "ewb_strategy_backtest.md",
        summary=summary,
        grouped=grouped,
        by_setup=by_setup,
        walk_forward=walk_forward,
        args=args,
    )
    print(f"Wrote {summary['outputs']['markdown']}")
    print(f"Scoped trades: {summary['scoped_rows']}")


if __name__ == "__main__":
    main()
