from __future__ import annotations

from pathlib import Path

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
from scripts.crypto_research_report import build_payload as build_crypto_research_payload
from scripts.crypto_research_report import markdown_report as crypto_research_markdown
from scripts.historical_signal_grid import (
    checkpoint_csv_path_for,
    checkpoint_path_for,
    read_checkpoint_frame,
    remove_checkpoint_files,
    write_trades_frame,
)
from scripts.pine_parity_checklist import build_crypto_markdown, representative_crypto_rows
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
from ewb.research.universe import CRYPTO
from ewb.strategy_system import (
    StrategyContract,
    append_jsonl,
    filter_contract_trades,
    forward_trades,
    grouped_summary,
    is_crypto_ticker,
    normalize_historical_trades,
    note_event,
    outcome_event,
    probability_percent,
    signal_event,
    signal_event_from_payload,
    trade_summary,
    walk_forward_summary,
)

REPO = Path(__file__).resolve().parents[2]


def test_cost_for_asset_classes():
    assert cost_for("AAPL") == 0.0008
    assert cost_for("SPY") == 0.0008
    assert cost_for("BTC-USD") == 0.0015
    assert cost_for("EURUSD=X") == 0.0013
    assert cost_for("GC=F") == 0.0013


def test_crypto_universe_uses_trx_instead_of_legacy_matic():
    assert "TRX-USD" in CRYPTO
    assert "MATIC-USD" not in CRYPTO


def test_strategy_system_probability_and_crypto_symbol_helpers():
    assert probability_percent(0.585) == pytest.approx(58.5)
    assert probability_percent("58.5") == pytest.approx(58.5)
    assert probability_percent(None) is None
    assert is_crypto_ticker("BTC-USD")
    assert is_crypto_ticker("BTCUSDT")
    assert is_crypto_ticker("BINANCE:BTCUSDT")
    assert is_crypto_ticker("CRYPTO:ETHUSD")
    assert not is_crypto_ticker("AAPL")


def test_strategy_system_contract_metrics_and_forward_log(tmp_path):
    raw = pd.DataFrame([
        {
            "ticker": "AAPL", "universe_rank": 1, "interval": "1h",
            "fig_type": "flat", "side": "long", "mtf_policy": "none",
            "entry_variant": "confirm_close", "entry_ts": "2026-01-01T10:00:00Z",
            "entry_px": 100.0, "p_win_model": 60.0, "sample_size": 50,
            "net_ret": 0.02, "win": True,
        },
        {
            "ticker": "MSFT", "universe_rank": 2, "interval": "1h",
            "fig_type": "triangle", "side": "short", "mtf_policy": "none",
            "entry_variant": "confirm_close", "entry_ts": "2026-01-02T10:00:00Z",
            "entry_px": 200.0, "p_win_model": 40.0, "sample_size": 50,
            "net_ret": -0.01, "win": False,
        },
        {
            "ticker": "NVDA", "universe_rank": 3, "interval": "4h",
            "fig_type": "double_corr", "side": "short", "mtf_policy": "none",
            "entry_variant": "confirm_close", "entry_ts": "2026-01-03T10:00:00Z",
            "entry_px": 300.0, "p_win_model": 58.0, "sample_size": 30,
            "net_ret": -0.01, "win": False,
        },
    ])
    trades = normalize_historical_trades(raw, asset_class="stock")
    scoped = filter_contract_trades(
        trades,
        contract=StrategyContract(),
        min_model_p=55.0,
        min_sample=20,
        intervals={"1h", "4h"},
        universe_limit=10,
    )

    assert set(scoped["fig_type"]) == {"flat", "double_corr"}
    assert "setup_key" in scoped
    assert "signal_id" in scoped
    metrics = trade_summary(scoped)
    assert metrics["trades"] == 2
    assert metrics["winrate"] == 0.5
    grouped = grouped_summary(scoped, ["interval", "fig_type"])
    assert set(grouped["fig_type"]) == {"flat", "double_corr"}
    folds = walk_forward_summary(scoped, folds=2)
    assert len(folds) == 2

    log_path = tmp_path / "forward.jsonl"
    signal = signal_event(
        ticker="TSLA",
        interval="1h",
        action="sell",
        entry_ts="2026-06-07T12:00:00Z",
        entry_px=390.0,
        stop_px=411.0,
        target_px=388.0,
        fig_type="double_corr",
        probability=54.5,
        htf_context="4H DOWN | 1D DOWN",
    )
    append_jsonl(log_path, signal)
    append_jsonl(log_path, outcome_event(
        signal_id=signal["signal_id"],
        exit_ts="2026-06-08T12:00:00Z",
        exit_px=388.0,
        exit_reason="tp",
    ))
    forward = forward_trades([signal, outcome_event(
        signal_id=signal["signal_id"],
        exit_ts="2026-06-08T12:00:00Z",
        exit_px=388.0,
        exit_reason="tp",
    )])
    assert forward.loc[0, "status"] == "closed"
    assert forward.loc[0, "win"]
    note = note_event(signal_id=signal["signal_id"], tag="late_entry", note="entered late")
    assert note["event_type"] == "note"
    assert note["tag"] == "late_entry"
    assert note["note"] == "entered late"

    alert = signal_event_from_payload({
        "symbol": "BTC-USD",
        "timeframe": "4h",
        "side": "buy",
        "time": "2026-06-07T16:00:00Z",
        "close": "70000",
        "sl": "68000",
        "tp": "74000",
        "pattern": "flat",
        "p_win": "58.5",
        "context": "1D UP | 1W UP",
    })
    assert alert["ticker"] == "BTC-USD"
    assert alert["side"] == "long"
    assert alert["entry_px"] == 70000.0
    assert alert["probability"] == 58.5
    assert alert["setup_key"].startswith("crypto|4h|flat|long")

    tv_alert = signal_event_from_payload({
        "symbol": "BINANCE:BTCUSDT",
        "timeframe": "4h",
        "side": "buy",
        "time": "2026-06-07T16:00:00Z",
        "close": "70000",
        "sl": "68000",
        "tp": "74000",
        "pattern": "flat",
        "p_win": "0.585",
    })
    assert tv_alert["ticker"] == "BINANCE:BTCUSDT"
    assert tv_alert["probability"] == pytest.approx(58.5)
    assert tv_alert["setup_key"].startswith("crypto|4h|flat|long")

    cancelled = signal_event(
        ticker="BTCUSDT",
        interval="4h",
        action="buy",
        entry_ts="2026-06-09T12:00:00Z",
        entry_px=70000.0,
        stop_px=68000.0,
        target_px=74000.0,
        fig_type="flat",
        probability=0.61,
    )
    cancelled_forward = forward_trades([cancelled, outcome_event(
        signal_id=cancelled["signal_id"],
        exit_ts="2026-06-09T13:00:00Z",
        exit_px=70000.0,
        exit_reason="cancelled",
    )])
    assert cancelled["probability"] == pytest.approx(61.0)
    assert cancelled["setup_key"].startswith("crypto|4h|flat|long")
    assert cancelled_forward.loc[0, "status"] == "cancelled"
    assert trade_summary(cancelled_forward[cancelled_forward["status"] == "closed"])["trades"] == 0


def test_strategy_system_scripts_exist():
    assert (REPO / "python" / "scripts" / "backtest_ewb_strategy.py").exists()
    assert (REPO / "python" / "scripts" / "forward_signal_logger.py").exists()
    assert (REPO / "python" / "scripts" / "forward_daily_report.py").exists()
    assert (REPO / "python" / "scripts" / "compare_backtest_forward.py").exists()
    assert (REPO / "python" / "scripts" / "run_dashboard.py").exists()
    assert (REPO / "python" / "ewb" / "web_dashboard.py").exists()
    assert (REPO / "scripts" / "run_strategy_system.sh").exists()
    assert (REPO / "configs" / "watchlist_profiles.yaml").exists()
    assert (REPO / "configs" / "risk_settings.yaml").exists()
    assert (REPO / "docs" / "strategy_system.md").exists()
    assert (REPO / "docs" / "local_dashboard.md").exists()


def test_pine_crypto_research_contract_is_static():
    mono = (REPO / "pine" / "ewb_monowaves_mtf.pine").read_text(encoding="utf-8")
    overlay = (REPO / "pine" / "ewb_probability_overlay_v0.pine").read_text(encoding="utf-8")

    for source in (mono, overlay):
        assert 'options = ["Stocks", "Crypto", "Auto", "Research any"]' in source
        assert '"Any"' not in source
        assert "crypto-v0 research" in source
        assert "marketActionable" in source or "actionableTradeSymbol" in source

    assert "enableCryptoActions" in mono
    assert "actionableCryptoSymbol" in mono
    assert 'marketMode = input.string("Auto", "Market mode"' in mono
    assert "CRYPTO LIVE\\nBUY/SELL ENABLED" in mono
    assert "crypto_v0|flat|4h|short" in mono
    assert "crypto_v0|double_corr|1h|short" in mono
    assert 'actionReason = not isMarketSupported ? "unsupported market" : isCryptoResearch ? "crypto research only - no trade"' in overlay
    assert "CRYPTO RESEARCH ONLY\\nNO BUY/SELL ALERTS" in overlay
    assert "displayPev = isMarketActionable" in overlay
    assert "displayEntry = isMarketActionable" in overlay


def test_pine_neely_core_signal_contract():
    mono = (REPO / "pine" / "ewb_monowaves_mtf.pine").read_text(encoding="utf-8")

    assert 'grpCore = "Neely Core signals (book-derived)"' in mono
    assert "hybridZigzagOK" in mono
    assert "hybridMovingFlatOK" in mono
    assert 'lastCoreSignal := "IMPULSE POST"' in mono
    assert 'lastCoreSignal := "TRIANGLE THRUST"' in mono
    assert 'lastCoreSignal := "ZIGZAG REVERSAL"' in mono
    assert 'lastCoreSignal := "MOVING CORR"' in mono
    assert 'alertcondition(coreSignalEvent, "EWB Neely Core Signal"' in mono
    assert 'alertcondition(coreTriangleEvent, "EWB Core TRIANGLE THRUST"' in mono
    assert 'grpAlerts = "Alerts / звук"' in mono
    assert "enableActionSoundAlerts" in mono
    assert "enableCoreSoundAlerts" in mono
    assert "actionAlertMessage" in mono
    assert '\\"source\\":\\"tradingview_pine\\"' in mono
    assert '\\"strategy_id\\":\\"ewb-anton-v1\\"' in mono
    assert '\\"entry_px\\":' in mono
    assert '\\"stop_px\\":' in mono
    assert '\\"target_px\\":' in mono
    assert '\\"htf_context\\":' in mono
    assert "actionAlertFigType" in mono
    assert "str.format_time(time" in mono
    assert "jsonString(syminfo.ticker)" in mono
    assert "coreAlertMessage" in mono
    assert "alert(actionAlertMessage" in mono
    assert "alert(coreAlertMessage" in mono
    assert "simpleAntonPanel" in mono
    assert "panelPositionInput" in mono
    assert 'showMarketBanner = input.bool(false, "Show market safety banner"' in mono
    assert 'showTradeMarkers = input.bool(false, "Show previous entries/exits"' in mono
    assert 'onlyLatestSignal = input.bool(true, "Only latest signal"' in mono
    assert "EXIT TP" in mono
    assert "EXIT SL" in mono
    assert "showNeelyWaveNumbers" in mono
    assert "showLatestPivotNumbers" in mono
    assert 'showLatestPivotNumbers = input.bool(false, "Show last pivot points"' in mono
    assert "latestPivotLabels" in mono
    assert '"P" + str.tostring(lp)' in mono
    assert 'grpHtfMap = "HTF wave map"' in mono
    assert "showHtfWaveMap" in mono
    assert "htfContextLevels" in mono
    assert "htfMapRightOffset" in mono
    assert "chartTfRank()" in mono
    assert "contextTfEnabled" in mono
    assert 'request.security(syminfo.tickerid, "60", high' in mono
    assert 'request.security(syminfo.tickerid, "240", high' in mono
    assert 'request.security(syminfo.tickerid, "D", high' in mono
    assert 'request.security(syminfo.tickerid, "W", high' in mono
    assert 'request.security(syminfo.tickerid, "M", high' in mono
    assert "drawHtfWaveMap" in mono
    assert "mtfContextStack" in mono
    assert "tfPlanBase" in mono
    assert 'tfPlanText = mtfContextStack == "" ? tfPlanBase : tfPlanBase + " | Map " + mtfContextStack' in mono
    assert "tfPlanShort" in mono
    assert "activeHtfDisplay" in mono
    assert "label.new(bar_index + htfMapRightOffset + xOffset" in mono
    assert "htfW3MainLabel := label.new(w3X1, activeHPrice" in mono
    assert 'grpHyp = "Live structure hypothesis"' in mono
    assert "showLiveHypothesis" in mono
    assert "showHypothesisLevels" in mono
    assert "readyHypothesisProb" in mono
    assert "preferLongTermTF" in mono
    assert 'grpHtfW3 = "HTF Wave-3 pullback mode"' in mono
    assert "showHtfWave3Bias" in mono
    assert "htfWave3PullbackOnly" in mono
    assert "minHtfWave3Prob" in mono
    assert "htfWave3BiasActive" in mono
    assert "htfPivotBars" in mono
    assert "htfWave3Prob := probFromScores" in mono
    assert "htfFocusScore()" in mono
    assert "htfRRScore, htfFocusScore())" in mono
    assert "htfWave3Plan" in mono
    assert "HTF W3 UP -> buy LTF pullbacks" in mono
    assert "HTF W3 DOWN -> sell LTF pullbacks" in mono
    assert "HTF W3 ONLY" in mono
    assert "waitNoEntryReason" in mono
    assert "WAIT PULLBACK" in mono
    assert "WAIT / NO COUNTER" in mono
    assert "displayHtfWave3" in mono
    assert "displayLiveContextLevels" in mono
    assert "displayLevels = liveAgainstHtfWave3 and htfWave3PullbackOnly ? displayHtfWave3Levels" in mono
    assert "displayProbabilityMove = liveAgainstHtfWave3 and htfWave3PullbackOnly ? displayHtfWave3Prob" in mono
    assert "HTF W2 invalid" in mono
    assert "HTF W3 TP1 1.618" in mono
    assert "HTF W3 TP2 2.618" in mono
    assert "scoreNear" in mono
    assert "probFromScores" in mono
    assert 'liveHypothesisName := "Dev Flat C"' in mono
    assert 'liveHypothesisName := "Dev WXY / Zigzag C"' in mono
    assert 'liveHypothesisName := "Dev Impulse W5"' in mono
    assert 'liveHypothesisName := "Dev Triangle e"' in mono
    assert 'liveHypothesisLabels := "0|A|B|C?"' in mono
    assert 'liveHypothesisLabels := "0|1|2|3|4|5?"' in mono
    assert "liveHypothesisReadyEvent" in mono
    assert 'alertcondition(liveHypothesisReadyEvent, "EWB Live Hypothesis Ready"' in mono
    assert "enableHypothesisSoundAlerts" in mono
    assert "displayPatternNow" in mono
    assert "Anton decision" in mono
    assert "ENTER LONG" in mono
    assert "EARLY LONG" in mono
    assert "WATCH LONG" in mono
    assert "HOLD / MANAGE" in mono
    assert "displayProbabilityState" in mono
    assert "Last plan: Entry/SL/MOVE levels remain visible" in mono
    assert "actionStateKey" in mono
    assert 'table.cell(info, 0, 3, "Reason"' in mono
    assert "LAST BAR WAVE" in mono
    assert 'table.cell(info, 0, 4, "Last bar wave"' in mono
    assert 'table.cell(info, 0, 5, "Live hypothesis"' in mono
    assert 'table.cell(info, 0, 6, "TF plan"' in mono
    assert 'table.cell(info, 0, 14, "HTF bias/W3"' in mono
    assert "tfPlanText" in mono
    assert "bestHypProb" not in mono
    assert "htfBlocksHyp" not in mono
    assert "for clearRow = degClearStart+2 to 23" in mono
    assert "MOVE 1.618" in mono
    assert "coreWaveLabel5" in mono
    assert 'table.cell(info, 0, 17, "Live hypothesis"' in mono
    assert 'table.cell(info, 0, 19, "Neely Core"' in mono


def test_neely_core_ab_backtest_contract():
    script = (REPO / "python" / "scripts" / "neely_core_ab_backtest.py").read_text(encoding="utf-8")

    assert "core_impulse_post_w4" in script
    assert "core_triangle_thrust" in script
    assert "core_zigzag_reversal_c_eq_a" in script
    assert "core_moving_correction_follow" in script
    assert "fib_primary_bucket" in script
    assert "baseline_flat_fade" in script
    assert "baseline_double_corr_fade" in script
    assert "--stock-provider" in script
    assert "tiingo-cache" in script
    assert "Data Coverage" in script
    assert "neely_core_ab_backtest_report.md" in script


def test_anton_winrate_optimizer_contract():
    script = (REPO / "python" / "scripts" / "anton_winrate_optimizer.py").read_text(encoding="utf-8")

    assert "Anton Winrate Optimizer" in script
    assert "breakeven_winrate" in script
    assert "wilson_lower_bound" in script
    assert "edge_over_breakeven" in script
    assert "fib_primary_near" in script
    assert "test_profit_factor" in script
    assert "anton_winrate_optimizer_report.md" in script


def test_historical_grid_checkpoint_helpers_clean_companions(tmp_path):
    trades_path = tmp_path / "historical_signal_grid_crypto_trades.parquet"
    checkpoint_path = checkpoint_path_for(str(trades_path))
    checkpoint_csv_path = checkpoint_csv_path_for(str(trades_path))
    df = pd.DataFrame([{"ticker": "BTC-USD", "interval": "1h", "value": 1.0}])

    written = write_trades_frame(df, checkpoint_path)
    assert written in {checkpoint_path, checkpoint_csv_path}
    loaded = read_checkpoint_frame(str(trades_path))
    assert loaded is not None
    assert loaded["ticker"].tolist() == ["BTC-USD"]

    pd.DataFrame([{"ticker": "TRX-USD", "interval": "1h", "value": 2.0}]).to_csv(
        checkpoint_csv_path,
        index=False,
    )
    remove_checkpoint_files(str(trades_path))
    assert not (tmp_path / "historical_signal_grid_crypto_trades_checkpoint.parquet").exists()
    assert not (tmp_path / "historical_signal_grid_crypto_trades_checkpoint.csv").exists()


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


def test_probability_calibration_script_deduplicates_grid_variants():
    from scripts.build_probability_calibration import canonical_trade_records

    trades = pd.DataFrame({
        "ticker": ["BTC-USD", "BTC-USD", "BTC-USD", "ETH-USD"],
        "interval": ["1h", "1h", "1h", "1h"],
        "fig_type": ["flat", "flat", "flat", "flat"],
        "side": ["long", "long", "long", "long"],
        "confirm_idx": [10, 10, 10, 20],
        "entry_ts": pd.to_datetime([
            "2026-01-01 00:00:00+00:00",
            "2026-01-01 00:00:00+00:00",
            "2026-01-01 00:00:00+00:00",
            "2026-01-02 00:00:00+00:00",
        ]),
        "entry_variant": ["next_bar_open", "next_bar_open", "confirm_close", "next_bar_open"],
        "mtf_policy": ["none", "none", "none", "none"],
        "tp_mult": [1.0, 1.618, 1.0, 1.0],
        "sl_mult": [1.0, 1.0, 1.0, 1.0],
        "exit_plan": ["full", "full", "full", "full"],
        "net_ret": [0.02, 0.03, 0.01, -0.01],
        "win": [True, True, True, False],
        "exit_reason": ["tp", "tp", "tp", "sl"],
    })
    canonical, meta = canonical_trade_records(trades, "crypto")
    assert meta["source_rows"] == 4
    assert meta["canonical_rows"] == 2
    assert len(canonical) == 2
    assert set(canonical["ticker"]) == {"BTC-USD", "ETH-USD"}


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


def test_crypto_pine_parity_checklist_is_research_only():
    trades = pd.DataFrame([
        {
            "ticker": "BTC-USD",
            "asset_class": "crypto",
            "interval": "1h",
            "fig_type": "flat",
            "side": "short",
            "entry_variant": "confirm_close",
            "mtf_policy": "none",
            "tp_mult": 1.0,
            "sl_mult": 1.0,
            "exit_plan": "full",
            "entry_ts": "2026-06-05 12:00:00+00:00",
            "entry_px": 100.0,
            "amp_pct": 0.10,
            "p_win_model": 73.0,
            "model_ev": 0.008,
        },
        {
            "ticker": "AAPL",
            "asset_class": "stocks",
            "interval": "1h",
            "fig_type": "flat",
            "side": "long",
            "entry_variant": "confirm_close",
            "mtf_policy": "none",
            "tp_mult": 1.0,
            "sl_mult": 1.0,
            "exit_plan": "full",
            "entry_ts": "2026-06-05 12:00:00+00:00",
            "entry_px": 100.0,
            "amp_pct": 0.10,
            "p_win_model": 0.55,
            "model_ev": 0.003,
        },
    ])
    rows = representative_crypto_rows(trades, limit=10)
    assert rows["ticker"].tolist() == ["BTC-USD"]

    markdown = build_crypto_markdown(trades, limit=10, source_path="crypto.parquet")
    assert "WAIT / crypto research" in markdown
    assert "crypto-v0 research" in markdown
    assert "73.0%" in markdown
    assert "BTC-USD" in markdown
    assert "AAPL" not in markdown


def test_crypto_pine_parity_checklist_hides_missing_model_ev():
    trades = pd.DataFrame([
        {
            "ticker": "BTC-USD",
            "asset_class": "crypto",
            "interval": "1h",
            "fig_type": "triangle",
            "side": "short",
            "entry_variant": "confirm_close",
            "mtf_policy": "none",
            "tp_mult": 1.0,
            "sl_mult": 1.0,
            "exit_plan": "full",
            "entry_ts": "2026-06-05 12:00:00+00:00",
            "entry_px": 100.0,
            "amp_pct": 0.10,
            "p_win_model": float("nan"),
            "model_ev": float("nan"),
        },
    ])

    markdown = build_crypto_markdown(trades, limit=10, source_path="crypto.parquet")
    assert "nan%" not in markdown
    assert "n/a / n/a" in markdown
    assert "WAIT / crypto research" in markdown


def test_crypto_research_report_keeps_wait_contract():
    trades = pd.DataFrame([
        {
            "ticker": "BTC-USD",
            "asset_class": "crypto",
            "interval": "1h",
            "fig_type": "flat",
            "side": "short",
            "entry_variant": "confirm_close",
            "mtf_policy": "none",
            "tp_mult": 1.0,
            "sl_mult": 1.0,
            "exit_plan": "full",
            "entry_ts": "2026-06-05 12:00:00+00:00",
            "entry_px": 100.0,
            "amp_pct": 0.10,
            "p_win_model": 73.0,
            "model_ev": 0.008,
            "confidence": "high",
            "sample_size": 120,
            "exit_reason": "tp",
            "net_ret": 0.02,
        },
        {
            "ticker": "AAPL",
            "asset_class": "stocks",
            "interval": "1h",
            "fig_type": "flat",
            "side": "long",
            "entry_variant": "confirm_close",
            "mtf_policy": "none",
            "tp_mult": 1.0,
            "sl_mult": 1.0,
            "exit_plan": "full",
            "entry_ts": "2026-06-05 12:00:00+00:00",
            "entry_px": 100.0,
            "amp_pct": 0.10,
            "p_win_model": 55.0,
            "model_ev": 0.003,
            "confidence": "high",
            "sample_size": 200,
            "exit_reason": "tp",
            "net_ret": 0.01,
        },
    ])
    payload = build_crypto_research_payload(trades, limit=10)
    assert payload["asset_class"] == "crypto"
    assert payload["mode"] == "research-only"
    assert payload["rows"][0]["ticker"] == "BTC-USD"
    assert payload["rows"][0]["action_now"] == "WAIT"
    assert payload["rows"][0]["reason"] == "CRYPTO_RESEARCH_ONLY"

    markdown = crypto_research_markdown(payload)
    assert "BTC-USD" in markdown
    assert "AAPL" not in markdown
    assert "Action now` is always `WAIT`" in markdown


def test_crypto_research_report_hides_missing_model_ev():
    trades = pd.DataFrame([
        {
            "ticker": "BTC-USD",
            "asset_class": "crypto",
            "interval": "1h",
            "fig_type": "impulse",
            "side": "short",
            "entry_variant": "confirm_close",
            "mtf_policy": "none",
            "tp_mult": 1.0,
            "sl_mult": 1.0,
            "exit_plan": "full",
            "entry_ts": "2026-06-05 12:00:00+00:00",
            "entry_px": 100.0,
            "amp_pct": 0.10,
            "p_win_model": float("nan"),
            "model_ev": float("nan"),
            "confidence": "none",
            "sample_size": 0,
            "exit_reason": "time",
            "net_ret": 0.0,
        },
    ])

    payload = build_crypto_research_payload(trades, limit=10)
    assert payload["rows"][0]["p_win"] is None
    assert payload["rows"][0]["expected_net_return"] is None
    markdown = crypto_research_markdown(payload)
    assert "nan%" not in markdown
    assert "| n/a | n/a |" in markdown




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
