# Pine crypto parity checklist

Источник: `/Users/DEV/Elliott-wave/python/data/historical_signal_grid_crypto_trades.parquet`
Последняя строка Python: `2026-06-05 13:15:00+00:00`
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
| ARB-USD | 15m | 2026-06-05 13:15:00+00:00 | impulse | SELL | WAIT / crypto research | 69.1% / +4.28% | 0.08 | 0.10 | 0.07 | Pine не должен превращать это в рабочий BUY/SELL |
| DOGE-USD | 15m | 2026-06-05 13:15:00+00:00 | impulse | SELL | WAIT / crypto research | 69.1% / +4.28% | 0.08 | 0.09 | 0.08 | Pine не должен превращать это в рабочий BUY/SELL |
| XRP-USD | 15m | 2026-06-05 13:15:00+00:00 | impulse | SELL | WAIT / crypto research | 69.1% / +4.28% | 1.13 | 1.21 | 1.06 | Pine не должен превращать это в рабочий BUY/SELL |
| APT-USD | 30m | 2026-06-05 12:30:00+00:00 | flat | SELL | WAIT / crypto research | 73.0% / +1.58% | 0.69 | 0.71 | 0.68 | Pine не должен превращать это в рабочий BUY/SELL |
| BTC-USD | 30m | 2026-06-05 12:00:00+00:00 | triangle | SELL | WAIT / crypto research | 56.9% / +1.43% | 62219.04 | 63273.94 | 61164.14 | Pine не должен превращать это в рабочий BUY/SELL |
| OP-USD | 30m | 2026-06-05 12:00:00+00:00 | flat | SELL | WAIT / crypto research | 73.0% / +1.58% | 0.10 | 0.11 | 0.10 | Pine не должен превращать это в рабочий BUY/SELL |
| ATOM-USD | 30m | 2026-06-05 11:30:00+00:00 | triangle | SELL | WAIT / crypto research | 56.9% / +1.43% | 1.70 | 1.74 | 1.66 | Pine не должен превращать это в рабочий BUY/SELL |
| BCH-USD | 30m | 2026-06-05 11:30:00+00:00 | flat | SELL | WAIT / crypto research | 73.0% / +1.58% | 223.00 | 237.20 | 208.80 | Pine не должен превращать это в рабочий BUY/SELL |
| BTC-USD | 15m | 2026-06-05 11:00:00+00:00 | flat | SELL | WAIT / crypto research | 73.0% / +1.58% | 62326.53 | 63247.43 | 61405.63 | Pine не должен превращать это в рабочий BUY/SELL |
| OP-USD | 15m | 2026-06-05 11:00:00+00:00 | triangle | SELL | WAIT / crypto research | 56.9% / +1.43% | 0.10 | 0.11 | 0.10 | Pine не должен превращать это в рабочий BUY/SELL |
| ADA-USD | 15m | 2026-06-05 10:30:00+00:00 | impulse | SELL | WAIT / crypto research | 69.1% / +4.28% | 0.17 | 0.21 | 0.12 | Pine не должен превращать это в рабочий BUY/SELL |
| FIL-USD | 15m | 2026-06-05 10:00:00+00:00 | impulse | SELL | WAIT / crypto research | 69.1% / +4.28% | 0.80 | 0.90 | 0.69 | Pine не должен превращать это в рабочий BUY/SELL |
| BCH-USD | 15m | 2026-06-05 09:15:00+00:00 | impulse | SELL | WAIT / crypto research | 69.1% / +4.28% | 227.10 | 259.20 | 195.00 | Pine не должен превращать это в рабочий BUY/SELL |
| LTC-USD | 30m | 2026-06-05 09:00:00+00:00 | impulse | SELL | WAIT / crypto research | 69.1% / +4.28% | 44.47 | 48.76 | 40.18 | Pine не должен превращать это в рабочий BUY/SELL |
| AVAX-USD | 15m | 2026-06-05 07:30:00+00:00 | impulse | SELL | WAIT / crypto research | 69.1% / +4.28% | 7.28 | 8.12 | 6.44 | Pine не должен превращать это в рабочий BUY/SELL |
| BNB-USD | 30m | 2026-06-05 07:30:00+00:00 | double_corr | BUY | WAIT / crypto research | 100.0% / +27.82% | 593.26 | 553.52 | 633.00 | Pine не должен превращать это в рабочий BUY/SELL |
| LTC-USD | 15m | 2026-06-05 07:30:00+00:00 | impulse | SELL | WAIT / crypto research | 69.1% / +4.28% | 44.03 | 48.32 | 39.74 | Pine не должен превращать это в рабочий BUY/SELL |
| ADA-USD | 30m | 2026-06-05 07:00:00+00:00 | flat | SELL | WAIT / crypto research | 73.0% / +1.58% | 0.16 | 0.18 | 0.14 | Pine не должен превращать это в рабочий BUY/SELL |
| APT-USD | 15m | 2026-06-05 06:15:00+00:00 | impulse | SELL | WAIT / crypto research | 69.1% / +4.28% | 0.69 | 0.80 | 0.58 | Pine не должен превращать это в рабочий BUY/SELL |
| ETC-USD | 15m | 2026-06-05 06:15:00+00:00 | impulse | SELL | WAIT / crypto research | 69.1% / +4.28% | 6.81 | 7.65 | 5.97 | Pine не должен превращать это в рабочий BUY/SELL |
| ETH-USD | 15m | 2026-06-05 06:15:00+00:00 | impulse | SELL | WAIT / crypto research | 69.1% / +4.28% | 1644.91 | 1813.56 | 1476.26 | Pine не должен превращать это в рабочий BUY/SELL |
| SOL-USD | 15m | 2026-06-05 06:15:00+00:00 | triangle | BUY | WAIT / crypto research | 40.4% / -0.54% | 64.65 | 56.72 | 72.58 | Pine не должен превращать это в рабочий BUY/SELL |
| UNI-USD | 15m | 2026-06-05 06:15:00+00:00 | triangle | BUY | WAIT / crypto research | 40.4% / -0.54% | 2.45 | 2.16 | 2.75 | Pine не должен превращать это в рабочий BUY/SELL |
| ARB-USD | 30m | 2026-06-05 06:00:00+00:00 | triangle | BUY | WAIT / crypto research | 40.4% / -0.54% | 0.08 | 0.07 | 0.10 | Pine не должен превращать это в рабочий BUY/SELL |

## Критерии прохождения

- На crypto-графике `Action now` остаётся `WAIT` независимо от найденной фигуры.
- Панель явно показывает `crypto-v0 research`, а не `stocks-v0`.
- `P≈`, `Entry / TP`, `SL` не выглядят как рабочий stock trade-plan для crypto.
- `alertcondition` BUY/SELL не срабатывает для crypto.
- Если Pine и Python по фигуре расходятся, это finding для будущей crypto parity, но не причина включать crypto-сделки.
