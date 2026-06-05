# Pine crypto parity checklist

Источник: `/Users/DEV/Elliott-wave/python/data/historical_signal_grid_crypto_trades.parquet`
Последняя строка Python: `2026-06-05 14:30:00+00:00`
Модель: `probability-calibration-crypto-v0` / research-only

Цель: вручную проверить, что Pine на crypto-графиках не использует stock-калибровку
как рабочий BUY/SELL. Crypto пока должен оставаться `WAIT / crypto research`, пока
отдельная crypto parity не станет production-ready.

Как проверять:
1. Открой crypto ticker в TradingView, например `BTCUSDT`, `ETHUSDT`, `SOLUSDT`.
2. Поставь TF из таблицы.
3. В `Elliott Wave Brain — Monowaves MTF` выставь `Market mode = Crypto`.
4. Ожидаемый результат: `Action now = WAIT`, `Reason = CRYPTO RESEARCH ONLY`, `Market = Crypto / crypto-v0 research`.
5. В `Market mode = Stocks` тот же график должен показывать `WAIT / unsupported crypto`.
6. Убедись, что BUY/SELL alerts не срабатывают на crypto.

## Crypto research rows

| Тикер | TF | Python entry_ts | Pattern | Python side | Ожидаемый Action now | P/EV | Entry | Stop | Target | Проверка |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| OP-USD | 15m | 2026-06-05 14:30:00+00:00 | double_corr | BUY | WAIT / crypto research | 82.4% / +2.23% | 0.10 | 0.09 | 0.11 | Pine не должен превращать это в рабочий BUY/SELL |
| ETH-USD | 15m | 2026-06-05 14:00:00+00:00 | flat | SELL | WAIT / crypto research | 55.9% / +0.70% | 1615.77 | 1647.06 | 1584.48 | Pine не должен превращать это в рабочий BUY/SELL |
| SOL-USD | 30m | 2026-06-05 14:00:00+00:00 | triangle | SELL | WAIT / crypto research | 40.3% / -0.18% | 64.87 | 64.90 | 64.84 | Pine не должен превращать это в рабочий BUY/SELL |
| ATOM-USD | 15m | 2026-06-05 13:45:00+00:00 | flat | SELL | WAIT / crypto research | 55.9% / +0.70% | 1.69 | 1.72 | 1.66 | Pine не должен превращать это в рабочий BUY/SELL |
| AVAX-USD | 15m | 2026-06-05 13:45:00+00:00 | flat | SELL | WAIT / crypto research | 55.9% / +0.70% | 6.97 | 7.19 | 6.76 | Pine не должен превращать это в рабочий BUY/SELL |
| BNB-USD | 15m | 2026-06-05 13:45:00+00:00 | flat | SELL | WAIT / crypto research | 55.9% / +0.70% | 581.02 | 586.62 | 575.42 | Pine не должен превращать это в рабочий BUY/SELL |
| DOT-USD | 15m | 2026-06-05 13:45:00+00:00 | triangle | SELL | WAIT / crypto research | 40.3% / -0.18% | 0.96 | 0.97 | 0.96 | Pine не должен превращать это в рабочий BUY/SELL |
| ETC-USD | 15m | 2026-06-05 13:45:00+00:00 | double_corr | SELL | WAIT / crypto research | 87.5% / +2.15% | 6.81 | 7.13 | 6.49 | Pine не должен превращать это в рабочий BUY/SELL |
| FIL-USD | 15m | 2026-06-05 13:45:00+00:00 | flat | SELL | WAIT / crypto research | 55.9% / +0.70% | 0.76 | 0.80 | 0.73 | Pine не должен превращать это в рабочий BUY/SELL |
| LTC-USD | 15m | 2026-06-05 13:45:00+00:00 | double_corr | SELL | WAIT / crypto research | 87.5% / +2.15% | 43.24 | 45.15 | 41.33 | Pine не должен превращать это в рабочий BUY/SELL |
| ETH-USD | 30m | 2026-06-05 13:30:00+00:00 | flat | SELL | WAIT / crypto research | 55.9% / +0.70% | 1615.04 | 1623.82 | 1606.26 | Pine не должен превращать это в рабочий BUY/SELL |
| LINK-USD | 30m | 2026-06-05 13:30:00+00:00 | flat | SELL | WAIT / crypto research | 55.9% / +0.70% | 7.38 | 7.51 | 7.25 | Pine не должен превращать это в рабочий BUY/SELL |
| ARB-USD | 15m | 2026-06-05 13:15:00+00:00 | impulse | SELL | WAIT / crypto research | 48.0% / -0.86% | 0.08 | 0.10 | 0.07 | Pine не должен превращать это в рабочий BUY/SELL |
| DOGE-USD | 15m | 2026-06-05 13:15:00+00:00 | impulse | SELL | WAIT / crypto research | 48.0% / -0.86% | 0.08 | 0.09 | 0.08 | Pine не должен превращать это в рабочий BUY/SELL |
| XRP-USD | 15m | 2026-06-05 13:15:00+00:00 | impulse | SELL | WAIT / crypto research | 48.0% / -0.86% | 1.13 | 1.21 | 1.06 | Pine не должен превращать это в рабочий BUY/SELL |
| APT-USD | 30m | 2026-06-05 12:30:00+00:00 | flat | SELL | WAIT / crypto research | 55.9% / +0.70% | 0.69 | 0.71 | 0.68 | Pine не должен превращать это в рабочий BUY/SELL |
| BTC-USD | 30m | 2026-06-05 12:00:00+00:00 | triangle | SELL | WAIT / crypto research | 40.3% / -0.18% | 62219.04 | 63273.94 | 61164.14 | Pine не должен превращать это в рабочий BUY/SELL |
| OP-USD | 30m | 2026-06-05 12:00:00+00:00 | flat | SELL | WAIT / crypto research | 55.9% / +0.70% | 0.10 | 0.11 | 0.10 | Pine не должен превращать это в рабочий BUY/SELL |
| ATOM-USD | 30m | 2026-06-05 11:30:00+00:00 | triangle | SELL | WAIT / crypto research | 40.3% / -0.18% | 1.70 | 1.74 | 1.66 | Pine не должен превращать это в рабочий BUY/SELL |
| BCH-USD | 30m | 2026-06-05 11:30:00+00:00 | flat | SELL | WAIT / crypto research | 55.9% / +0.70% | 223.00 | 237.20 | 208.80 | Pine не должен превращать это в рабочий BUY/SELL |
| BTC-USD | 15m | 2026-06-05 11:00:00+00:00 | flat | SELL | WAIT / crypto research | 55.9% / +0.70% | 62326.53 | 63247.43 | 61405.63 | Pine не должен превращать это в рабочий BUY/SELL |
| OP-USD | 15m | 2026-06-05 11:00:00+00:00 | triangle | SELL | WAIT / crypto research | 40.3% / -0.18% | 0.10 | 0.11 | 0.10 | Pine не должен превращать это в рабочий BUY/SELL |
| ADA-USD | 15m | 2026-06-05 10:30:00+00:00 | impulse | SELL | WAIT / crypto research | 48.0% / -0.86% | 0.17 | 0.21 | 0.12 | Pine не должен превращать это в рабочий BUY/SELL |
| TRX-USD | 15m | 2026-06-05 10:30:00+00:00 | flat | BUY | WAIT / crypto research | 56.4% / +0.57% | 0.33 | 0.32 | 0.33 | Pine не должен превращать это в рабочий BUY/SELL |

## Критерии прохождения

- На crypto-графике `Action now` остаётся `WAIT` независимо от найденной фигуры.
- Панель явно показывает `crypto-v0 research`, а не `stocks-v0`.
- Crypto calibration сверяется по canonical unique signals, а не по grid-вариантам TP/SL/MTF.
- `P≈`, `Entry / TP`, `SL` не выглядят как рабочий stock trade-plan для crypto.
- `alertcondition` BUY/SELL не срабатывает для crypto.
- Источник данных указан как Binance spot klines; расхождения с TradingView venue/timezone заносятся как data finding.
- Тикеры с миграцией/плохими данными, например `MATIC/POL`, не используются для production defaults без отдельной проверки.
- Если Pine и Python по фигуре расходятся, это finding для будущей crypto parity, но не причина включать crypto-сделки.
