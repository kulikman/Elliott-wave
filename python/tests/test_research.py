from __future__ import annotations

import pandas as pd
import pytest

from ewb.confirm import CheckResult
from ewb.figures import Figure
from ewb.monowaves import Pivot
from scripts import build_dataset
from scripts.daily_report import (
    decision_reason,
    load_watchlist,
    risk_metrics,
    russian_daily_report,
    save_daily_outputs,
    signal_strength,
    sort_daily_signals,
)
from scripts.scan_probability_signals import (
    build_payload,
    filter_fresh_signals,
    markdown_report,
    save_outputs,
)
from ewb.research import (
    build_probability_signal,
    build_probability_calibration,
    calibration_rows,
    confidence_for_n,
    cost_for,
    exit_for_trade,
    figure_rows_from_matches,
    fmt_df,
    hypothesis_table,
    log_processing_error,
    normalize_ohlc,
    portfolio_metrics,
    fade_side,
    lookup_probability_row,
    price_levels,
    probability_signal_from_figure,
    recommended_action,
    side_probabilities,
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


def test_probability_helpers_map_action_confidence_and_side():
    assert confidence_for_n(10) == "low"
    assert confidence_for_n(50) == "medium"
    assert confidence_for_n(150) == "high"
    assert confidence_for_n(400) == "very_high"
    assert recommended_action("flat", "long") == "buy"
    assert recommended_action("double_corr", "short") == "sell"
    assert recommended_action("triangle", "long") == "skip"
    assert fade_side("up") == "short"
    assert fade_side("down") == "long"
    assert side_probabilities("long", 0.6) == pytest.approx((0.6, 0.4))
    assert side_probabilities("short", 0.6) == pytest.approx((0.4, 0.6))
    assert price_levels("long", 100.0, 5.0) == {
        "entry_px": 100.0,
        "stop_px": 95.0,
        "target_px": 105.0,
    }
    assert price_levels("short", 100.0, 5.0) == {
        "entry_px": 100.0,
        "stop_px": 105.0,
        "target_px": 95.0,
    }


def test_probability_calibration_rows_build_indicator_contract():
    trades = pd.DataFrame({
        "fig_type": ["flat", "flat", "triangle"],
        "interval": ["1h", "1h", "1h"],
        "side": ["long", "long", "short"],
        "net_ret": [0.02, -0.01, -0.03],
        "win": [True, False, False],
        "exit_reason": ["tp", "sl", "time"],
    })
    rows = calibration_rows(trades, ["fig_type", "interval", "side"])
    flat = next(row for row in rows if row["fig_type"] == "flat")
    triangle = next(row for row in rows if row["fig_type"] == "triangle")
    assert flat["key"] == "flat|1h|long"
    assert flat["recommended_action"] == "buy"
    assert flat["p_trade_win"] == pytest.approx(0.5)
    assert flat["p_up"] == pytest.approx(0.5)
    assert flat["expected_net_return"] == pytest.approx(0.005)
    assert triangle["recommended_action"] == "skip"

    payload = build_probability_calibration(trades)
    assert payload["model_version"] == "probability-calibration-v0"
    assert payload["lookup_priority"][0] == "fig_type+interval+side"
    assert len(payload["rows"]) > len(rows)


def test_probability_signal_uses_lookup_priority_and_risk_box():
    trades = pd.DataFrame({
        "fig_type": ["flat", "flat", "triangle", "double_corr"],
        "interval": ["1h", "1h", "1h", "1d"],
        "side": ["long", "long", "short", "short"],
        "net_ret": [0.02, -0.01, -0.03, 0.04],
        "win": [True, False, False, True],
        "exit_reason": ["tp", "sl", "time", "tp"],
    })
    payload = build_probability_calibration(trades)
    row = lookup_probability_row(payload, "flat", "1h", "long")
    assert row["key"] == "flat|1h|long"

    signal = build_probability_signal(
        payload,
        fig_type="flat",
        interval="1h",
        direction="down",
        entry_px=100.0,
        amplitude=4.0,
    )
    assert signal["recommended_action"] == "buy"
    assert signal["side"] == "long"
    assert signal["lookup_key"] == "flat|1h|long"
    assert signal["p_trade_win"] == pytest.approx(0.5)
    assert signal["risk_box"]["stop_px"] == pytest.approx(96.0)
    assert signal["risk_box"]["target_px"] == pytest.approx(104.0)

    skip = build_probability_signal(
        payload,
        fig_type="triangle",
        interval="1h",
        direction="up",
        entry_px=100.0,
        amplitude=4.0,
    )
    assert skip["recommended_action"] == "skip"
    assert skip["stop"] == "none"
    assert skip["target"] == "none"
    assert skip["risk_box"]["stop_px"] is None
    assert skip["risk_box"]["target_px"] is None


def test_probability_signal_from_figure_uses_confirmation_entry():
    trades = pd.DataFrame({
        "fig_type": ["flat", "flat"],
        "interval": ["1h", "1h"],
        "side": ["long", "long"],
        "net_ret": [0.02, -0.01],
        "win": [True, False],
        "exit_reason": ["tp", "sl"],
    })
    payload = build_probability_calibration(trades)
    df = pd.DataFrame(
        {
            "open": [100, 101, 102, 103, 104, 105],
            "high": [101, 102, 103, 104, 105, 106],
            "low": [99, 100, 101, 102, 103, 104],
            "close": [100, 101, 102, 103, 104, 105],
        },
        index=pd.date_range("2024-01-01", periods=6, freq="1h"),
    )
    pivots = [
        Pivot(idx=0, price=100, direction=-1, confirmation_idx=0),
        Pivot(idx=2, price=104, direction=1, confirmation_idx=4),
        Pivot(idx=3, price=101, direction=-1, confirmation_idx=5),
    ]
    fig = Figure(
        type="flat",
        direction="down",
        start_idx=0,
        end_idx=3,
        pivots=pivots,
        checks=[CheckResult(True, "O", "ok", "AKU-test")],
    )
    signal = probability_signal_from_figure(payload, fig, df, "TEST", "1h")
    assert signal is not None
    assert signal["ticker"] == "TEST"
    assert signal["entry_idx"] == 5
    assert signal["risk_box"]["entry_px"] == 105
    assert signal["confirmation_lag"] == 2
    assert signal["recommended_action"] == "buy"
    assert signal["lookup_key"] == "flat|1h|long"


def test_probability_scan_payload_markdown_and_save(tmp_path):
    signal = {
        "ticker": "AAPL",
        "recommended_action": "buy",
        "pattern": "flat",
        "entry_ts": "2026-01-01 10:00:00",
        "p_trade_win": 0.55,
        "expected_net_return": 0.004,
        "confidence": "high",
        "risk_box": {
            "entry_px": 100.0,
            "stop_px": 96.0,
            "target_px": 104.0,
        },
    }
    payload = build_payload(
        [signal],
        tickers=["AAPL"],
        interval="1h",
        period="730d",
        actions={"buy", "sell"},
        limit=10,
        calibration={"model_version": "probability-calibration-v0"},
        fresh_hours=48,
    )
    assert payload["n_signals"] == 1
    assert payload["freshness"] == "48h"
    report = markdown_report(payload)
    assert "| AAPL | buy | flat |" in report
    assert "Freshness: `48h`" in report
    assert "55.0%" in report
    json_path, md_path = save_outputs(payload, str(tmp_path))
    assert json_path.endswith("probability_signals_1h_buy-sell_fresh-48h.json")
    assert md_path.endswith("probability_signals_1h_buy-sell_fresh-48h.md")
    assert "Probability Signals" in tmp_path.joinpath("probability_signals_1h_buy-sell_fresh-48h.md").read_text()


def test_filter_fresh_signals_keeps_only_recent_entries():
    now = pd.Timestamp("2026-06-05T12:00:00Z").to_pydatetime()
    signals = [
        {"entry_ts": "2026-06-05 09:00:00+00:00", "ticker": "FRESH"},
        {"entry_ts": "2026-06-03 09:00:00+00:00", "ticker": "OLD"},
        {"entry_ts": None, "ticker": "BAD"},
    ]
    fresh = filter_fresh_signals(signals, fresh_hours=24, now=now)
    assert [signal["ticker"] for signal in fresh] == ["FRESH"]


def test_daily_report_watchlist_and_russian_output(tmp_path):
    cfg = tmp_path / "watchlist.yaml"
    cfg.write_text(
        """
tickers:
  - aapl
  - MSFT
interval: 1h
actions:
  - buy
  - sell
fresh_hours: 48
limit: 5
""",
        encoding="utf-8",
    )
    config = load_watchlist(str(cfg))
    assert config["tickers"] == ["AAPL", "MSFT"]
    assert config["actions"] == ["buy", "sell"]
    payload = {
        "generated_at": "2026-06-05T06:00:00+00:00",
        "model_version": "probability-calibration-v0",
        "tickers": ["AAPL"],
        "interval": "1h",
        "freshness": "48h",
        "n_signals": 1,
        "no_signal_tickers": ["MSFT"],
        "last_signal_by_ticker": {
            "MSFT": {
                "ticker": "MSFT",
                "recommended_action": "skip",
                "pattern": "triangle",
                "entry_ts": "2026-06-02 09:30:00-04:00",
                "p_trade_win": 0.44,
                "expected_net_return": -0.001,
            },
        },
        "signals": [{
            "ticker": "AAPL",
            "recommended_action": "buy",
            "pattern": "flat",
            "entry_ts": "2026-06-05 09:30:00-04:00",
            "p_trade_win": 0.55,
            "expected_net_return": 0.004,
            "confidence": "high",
            "risk_box": {"entry_px": 100.0, "stop_px": 96.0, "target_px": 104.0},
        }],
    }
    report = russian_daily_report(payload)
    assert "Ежедневный отчёт сигналов" in report
    assert "ПОКУПАТЬ" in report
    assert "Без свежего торгового сигнала" in report
    assert "MSFT" in report
    assert "ПРОПУСТИТЬ" in report
    assert "triangle" in report
    assert "Причина" in report
    assert "Сила" in report
    assert "Детали свежих сигналов" in report
    assert "Риск/потенциал" in report
    assert "R:R" in report
    assert "| AAPL | A | ПОКУПАТЬ | flat | 55.0% | +0.40% | 100.00 | 96.00 | 104.00 |" in report
    assert "- Риск/потенциал: риск на акцию `4.00`, потенциал `4.00`, R:R `1.00`" in report
    assert "| MSFT | Skip |" in report
    assert "исторически даёт торговый edge" in report
    assert "no-trade паттерн" in report
    json_path, md_path = save_daily_outputs(payload, str(tmp_path))
    assert json_path.endswith("daily_report.json")
    assert md_path.endswith("daily_report.md")
    assert "ПОКУПАТЬ" in tmp_path.joinpath("daily_report.md").read_text(encoding="utf-8")


def test_daily_report_decision_reason():
    buy_reason = decision_reason({
        "recommended_action": "buy",
        "pattern": "flat",
        "p_trade_win": 0.55,
        "expected_net_return": 0.004,
        "confidence": "high",
    })
    skip_reason = decision_reason({
        "recommended_action": "skip",
        "pattern": "triangle",
        "p_trade_win": 0.40,
        "expected_net_return": -0.0018,
    })
    wait_reason = decision_reason({
        "recommended_action": "wait",
        "pattern": "unknown",
    })
    assert "торговый edge" in buy_reason
    assert "EV +0.40%" in buy_reason
    assert "no-trade паттерн" in skip_reason
    assert "лучше ждать" in wait_reason


def test_daily_report_signal_strength():
    assert signal_strength({
        "recommended_action": "buy",
        "p_trade_win": 0.56,
        "expected_net_return": 0.004,
        "confidence": "high",
    }) == "A"
    assert signal_strength({
        "recommended_action": "sell",
        "p_trade_win": 0.53,
        "expected_net_return": 0.001,
        "confidence": "medium",
    }) == "B"
    assert signal_strength({
        "recommended_action": "buy",
        "p_trade_win": 0.51,
        "expected_net_return": -0.001,
        "confidence": "high",
    }) == "C"
    assert signal_strength({"recommended_action": "skip"}) == "Skip"
    assert signal_strength({"recommended_action": "wait"}) == "Wait"


def test_daily_report_risk_metrics():
    metrics = risk_metrics({
        "risk_box": {
            "entry_px": 100.0,
            "stop_px": 96.0,
            "target_px": 104.0,
        },
    })
    assert metrics["risk_per_share"] == pytest.approx(4.0)
    assert metrics["reward_per_share"] == pytest.approx(4.0)
    assert metrics["rr"] == pytest.approx(1.0)
    assert risk_metrics({"risk_box": {"entry_px": 100.0}})["rr"] is None


def test_daily_report_sorts_by_strength_ev_then_recency():
    signals = [
        {
            "ticker": "CNEW",
            "recommended_action": "buy",
            "p_trade_win": 0.51,
            "expected_net_return": 0.001,
            "confidence": "high",
            "entry_ts": "2026-06-05 10:00:00+00:00",
        },
        {
            "ticker": "BOLD",
            "recommended_action": "buy",
            "p_trade_win": 0.53,
            "expected_net_return": 0.006,
            "confidence": "medium",
            "entry_ts": "2026-06-04 10:00:00+00:00",
        },
        {
            "ticker": "AOLD",
            "recommended_action": "sell",
            "p_trade_win": 0.56,
            "expected_net_return": 0.004,
            "confidence": "high",
            "entry_ts": "2026-06-03 10:00:00+00:00",
        },
        {
            "ticker": "ANEW",
            "recommended_action": "sell",
            "p_trade_win": 0.56,
            "expected_net_return": 0.004,
            "confidence": "high",
            "entry_ts": "2026-06-05 10:00:00+00:00",
        },
    ]
    assert [signal["ticker"] for signal in sort_daily_signals(signals)] == [
        "ANEW",
        "AOLD",
        "BOLD",
        "CNEW",
    ]


def test_daily_report_empty_message():
    payload = {
        "generated_at": "2026-06-05T06:00:00+00:00",
        "model_version": "probability-calibration-v0",
        "tickers": ["AAPL"],
        "interval": "1h",
        "freshness": "48h",
        "n_signals": 0,
        "signals": [],
    }
    report = russian_daily_report(payload)
    assert "Свежих торговых сигналов нет." in report




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
