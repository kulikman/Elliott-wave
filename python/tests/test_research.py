from __future__ import annotations

import pandas as pd
import pytest

from ewb.confirm import CheckResult
from ewb.figures import Figure
from ewb.monowaves import Pivot
from scripts import build_dataset
from ewb.research import (
    cost_for,
    exit_for_trade,
    figure_rows_from_matches,
    fmt_df,
    hypothesis_table,
    log_processing_error,
    normalize_ohlc,
    portfolio_metrics,
    stats_row,
    t_test,
    trade_metrics,
    validate_figure_rows,
    validate_trade_records,
)


def test_cost_for_asset_classes():
    assert cost_for("AAPL") == 0.0008
    assert cost_for("SPY") == 0.0008
    assert cost_for("BTC-USD") == 0.0013
    assert cost_for("EURUSD=X") == 0.0013
    assert cost_for("GC=F") == 0.0013


def test_normalize_ohlc_lowercases_and_filters_columns():
    raw = pd.DataFrame({
        "Open": [1.0, 2.0, 3.0],
        "High": [2.0, 3.0, 4.0],
        "Low": [0.5, 1.5, 2.5],
        "Close": [1.5, 2.5, 3.5],
        "Volume": [100, 200, 300],
        "Ignored": [9, 9, 9],
    })
    out = normalize_ohlc(raw, include_volume=True, min_rows=1)
    assert out is not None
    assert list(out.columns) == ["open", "high", "low", "close", "volume"]


def test_portfolio_metrics_sizes_from_amp_pct():
    trades = [{
        "entry_ts": "2024-01-01",
        "exit_ts": "2024-01-02",
        "amp_pct": 0.10,
        "net_ret": 0.02,
    }]
    metrics = portfolio_metrics(trades, initial=100_000, risk=0.01, max_conc=10)
    assert metrics is not None
    assert metrics["n"] == 1
    assert metrics["final"] == 100_200


def test_portfolio_metrics_can_disable_min_sl_floor():
    trades = [{
        "entry_ts": "2024-01-01",
        "exit_ts": "2024-01-02",
        "amp_pct": 0.0,
        "net_ret": 0.02,
    }]
    assert portfolio_metrics(trades, initial=100_000, min_sl_dist=0.0) is None
    metrics = portfolio_metrics(trades, initial=100_000)
    assert metrics is not None
    assert metrics["final"] == 101_000


def test_validate_trade_records_rejects_missing_required_columns():
    with pytest.raises(ValueError, match="amp_pct"):
        validate_trade_records([{
            "entry_ts": "2024-01-01",
            "exit_ts": "2024-01-02",
            "net_ret": 0.02,
        }])


def test_validate_figure_rows_requires_horizon_columns():
    row = {
        "ticker": "AAPL",
        "interval": "1d",
        "end_ts": "2024-01-01",
        "entry_ts": "2024-01-02",
        "confirmation_lag": 1,
        "fig_type": "flat",
        "direction": "up",
        "amp_pct": 0.05,
        "htf_bias": 1,
        "with_htf": True,
        "against_htf": False,
        "entry_px": 100.0,
        "ret_5": 0.01,
        "signed_ret_5": -0.01,
    }
    validate_figure_rows([row], horizons=(5,))
    with pytest.raises(ValueError, match="signed_ret_10"):
        validate_figure_rows([row], horizons=(5, 10))


def test_log_processing_error(capsys):
    log_processing_error("AAPL", "1d", ValueError("bad data"), context="test")
    captured = capsys.readouterr()
    assert "[skip:test] AAPL 1d: ValueError: bad data" in captured.out


def test_exit_for_trade_preserves_sl_tp_and_time_rules():
    close = [100.0, 101.0, 102.0, 103.0]
    high = [100.0, 111.0, 102.0, 103.0]
    low = [100.0, 89.0, 102.0, 103.0]

    assert exit_for_trade(high, low, close, 0, 100.0, +1, 3, 10.0, True) == (1, 90.0, "sl")
    assert exit_for_trade(high, low, close, 0, 100.0, -1, 3, 10.0, True) == (1, 110.0, "sl")
    assert exit_for_trade(high, low, close, 0, 100.0, +1, 2, 10.0, False) == (2, 102.0, "time")


def test_edge_stats_helpers_group_and_format():
    assert pd.isna(t_test(pd.Series([0.1, -0.1]), min_n=3)[0])

    row = stats_row(pd.Series([0.01, 0.02, -0.01]), min_n=1)
    assert row is not None
    assert row["n"] == 3
    assert row["hit_rate"] == pytest.approx(2 / 3)

    df = pd.DataFrame({
        "fig_type": ["flat", "flat", "flat", "triangle", "triangle"],
        "signed_ret_5": [0.01, 0.02, -0.01, 0.03, -0.02],
    })
    table = hypothesis_table(df, "fig_type", 5, "signed_ret", min_n=2)
    assert set(table["fig_type"]) == {"flat", "triangle"}
    assert "| fig_type" in fmt_df(table, cols_pct=["hit_rate"], cols_round=["sharpe"])


def test_trade_metrics_compounds_returns_and_profit_factor():
    trades = pd.DataFrame({
        "entry_ts": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
        "net_ret": [0.10, -0.05, 0.02],
        "win": [True, False, True],
    })
    metrics = trade_metrics(trades)
    assert metrics["n_trades"] == 3
    assert metrics["win_rate"] == pytest.approx(2 / 3)
    assert metrics["total_ret"] == pytest.approx((1.10 * 0.95 * 1.02) - 1)
    assert metrics["max_dd"] == pytest.approx(-0.05)
    assert metrics["profit_factor"] == pytest.approx(2.4)


def test_figures_to_rows_uses_confirmation_idx_for_entry(monkeypatch):
    monkeypatch.setattr(build_dataset, "HORIZONS", [1])
    df = pd.DataFrame(
        {
            "open": [100, 101, 102, 103, 104, 105],
            "high": [101, 102, 103, 104, 105, 106],
            "low": [99, 100, 101, 102, 103, 104],
            "close": [100, 101, 102, 103, 104, 105],
        },
        index=pd.date_range("2024-01-01", periods=6, freq="1D"),
    )
    pivots = [
        Pivot(idx=0, price=100, direction=-1, confirmation_idx=0),
        Pivot(idx=2, price=104, direction=1, confirmation_idx=4),
        Pivot(idx=3, price=101, direction=-1, confirmation_idx=5),
    ]
    fig = Figure(
        type="flat",
        direction="up",
        start_idx=0,
        end_idx=2,
        pivots=pivots[:2],
        checks=[CheckResult(True, "O", "ok", "AKU-test")],
    )
    rows = build_dataset.figures_to_rows(
        df,
        [fig],
        pd.Series(0, index=df.index),
        "TEST",
        "1d",
    )
    assert rows[0]["entry_ts"] == df.index[4]
    assert rows[0]["confirmation_lag"] == 2


def test_figure_rows_from_matches_can_preserve_extra_tf_schema():
    df = pd.DataFrame(
        {
            "open": [100, 101, 102, 103, 104, 105],
            "high": [101, 102, 103, 104, 105, 106],
            "low": [99, 100, 101, 102, 103, 104],
            "close": [100, 101, 102, 103, 104, 105],
        },
        index=pd.date_range("2024-01-01", periods=6, freq="1D"),
    )
    pivots = [
        Pivot(idx=0, price=100, direction=-1, confirmation_idx=0),
        Pivot(idx=1, price=103, direction=1, confirmation_idx=1),
        Pivot(idx=2, price=101, direction=-1, confirmation_idx=2),
        Pivot(idx=3, price=104, direction=1, confirmation_idx=3),
        Pivot(idx=4, price=102, direction=-1, confirmation_idx=4),
    ]
    fig = Figure(
        type="triangle",
        direction="down",
        start_idx=0,
        end_idx=4,
        pivots=pivots,
        checks=[CheckResult(True, "O", "ok", "AKU-test")],
    )
    rows = figure_rows_from_matches(
        df,
        [fig],
        pd.Series(0, index=df.index),
        "TEST",
        "15m",
        horizons=(1,),
        include_w5_ratio=False,
    )
    assert rows[0]["entry_ts"] == df.index[4]
    assert "w5_w3_ratio" not in rows[0]
