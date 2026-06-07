# TradingView Alert Bridge

Этот слой нужен, чтобы каждый сигнал индикатора попадал в forward-журнал и потом сравнивался с историческим baseline.

## Alert message

Основной способ: в TradingView создай alert с условием `Any alert() function call`.
Индикатор `Elliott Wave Brain — Monowaves MTF` сам отправит JSON, когда `Action now` станет `BUY` или `SELL`.

В alert message в этом режиме ничего вручную собирать не нужно: используется `alert(actionAlertMessage, ...)` из Pine.

## Manual alert message

Если нужно проверить цепочку вручную, вставляй JSON. Минимальный формат:

```json
{
  "source": "tradingview",
  "ticker": "{{ticker}}",
  "interval": "{{interval}}",
  "action": "buy",
  "entry_ts": "{{time}}",
  "entry_px": "{{close}}",
  "stop_px": 0,
  "target_px": 0,
  "fig_type": "flat",
  "probability": 0,
  "htf_context": "manual"
}
```

Для `sell` меняется только `"action": "sell"`.

Поля `stop_px`, `target_px`, `fig_type`, `probability`, `htf_context` должны приходить из индикатора или заполняться вручную при ручной проверке. Если Pine не может подставить динамическое значение в alertcondition message, используй TradingView alert по условию и затем импортируй JSON вручную из панели индикатора.

## Import alert

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

Команда вернет `signal_id`. Его нужно сохранить для закрытия сделки.

## Settle trade

```bash
python3 python/scripts/forward_signal_logger.py settle \
  --signal-id <signal_id> \
  --exit-ts 2026-06-14T16:00:00Z \
  --exit-px 210.80 \
  --exit-reason tp
```

Допустимые причины выхода: `tp`, `sl`, `time`, `manual`, `cancelled`.

## Summary

```bash
python3 python/scripts/forward_signal_logger.py summary
python3 python/scripts/forward_daily_report.py
python3 python/scripts/compare_backtest_forward.py
```

## Решение по боту

- 0-29 закрытых forward-сделок: только наблюдение.
- 30-99 сделок: можно оценивать стабильность, но без увеличения риска.
- 100+ сделок: сравнивать с baseline по winrate, expectancy, PF и просадке.
- Если forward expectancy ниже 0 или PF ниже 1.1, бот не включается на реальные деньги.
