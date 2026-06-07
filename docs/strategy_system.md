# EWB Strategy System

Отдельная система вокруг индикатора нужна, чтобы не путать красивую картинку на графике с доказанным торговым edge.

## Слои

## Ежедневный запуск

Основная команда для paper-trading контроля:

```bash
scripts/run_strategy_system.sh
```

Она обновляет baseline, строит forward daily report и сравнение backtest vs forward.

Лог:

- `brain-output/backtests/logs/strategy_system.log`

1. **Pine indicator**
   Визуальный слой и alerts: волны, HTF context, entry/SL/TP, решение Anton.

2. **Historical backtest**
   Python берет уже рассчитанные research trades и строит baseline:

   ```bash
   python3 python/scripts/backtest_ewb_strategy.py --asset-class both --intervals 1h 4h 1d 1w
   ```

   Выходы:
   - `brain-output/backtests/ewb_strategy_backtest.md`
   - `brain-output/backtests/ewb_strategy_backtest_summary.json`
   - `brain-output/backtests/ewb_strategy_backtest_trades.parquet`

3. **Forward journal**
   Каждый реальный alert записывается в журнал:

   ```bash
   python3 python/scripts/forward_signal_logger.py add --event-json '{
     "source": "tradingview",
     "ticker": "AAPL",
     "interval": "1d",
     "action": "buy",
     "entry_ts": "2026-06-07T16:00:00Z",
     "entry_px": 195.25,
     "stop_px": 188.40,
     "target_px": 210.80,
     "fig_type": "flat",
     "probability": 61.2,
     "htf_context": "1W UP | 1D W3?"
   }'
   ```

   Ручной режим тоже доступен:

   ```bash
   python3 python/scripts/forward_signal_logger.py add \
     --ticker TSLA \
     --interval 1h \
     --action sell \
     --entry-ts 2026-06-07T12:00:00Z \
     --entry-px 390.88 \
     --stop-px 411.33 \
     --target-px 388.06 \
     --fig-type double_corr \
     --probability 54.5 \
     --htf-context "4H DOWN | 1D DOWN"
   ```

   Когда сделка закрылась:

   ```bash
   python3 python/scripts/forward_signal_logger.py settle \
     --signal-id <id> \
     --exit-ts 2026-06-08T12:00:00Z \
     --exit-px 388.06 \
     --exit-reason tp
   ```

4. **Backtest vs forward**
   Сравнение истории с реальными сигналами:

   ```bash
   python3 python/scripts/forward_daily_report.py
   python3 python/scripts/compare_backtest_forward.py
   ```

   Выходы:
   - `brain-output/backtests/ewb_forward_daily_report.md`
   - `brain-output/backtests/ewb_forward_daily_report.json`
   - `brain-output/backtests/ewb_backtest_vs_forward.md`
   - `brain-output/backtests/ewb_backtest_vs_forward.json`
   - `brain-output/backtests/ewb_forward_trades.parquet`

## Правило запуска бота

- Меньше 30 закрытых forward-сделок: только наблюдение.
- Forward expectancy ниже 0: не включать реальные деньги.
- Profit factor ниже 1.1: не увеличивать размер.
- Сильное отличие forward winrate от истории: проверять repaint, задержку alert, цену исполнения, HTF context.

## Что логировать

- `ticker`
- `interval`
- `fig_type`
- `side`
- `entry_ts`
- `entry_px`
- `stop_px`
- `target_px`
- `probability`
- `htf_context`
- `exit_ts`
- `exit_px`
- `exit_reason`

## Важное ограничение

Исторический backtest нужен для скорости. Forward-журнал нужен для правды. Бота нельзя считать готовым, пока forward-журнал не подтверждает исторический edge.

Подробный формат TradingView alert описан в `docs/tradingview_alert_bridge.md`.
