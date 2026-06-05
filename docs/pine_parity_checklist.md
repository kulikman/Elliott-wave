# Pine parity checklist

Источник: `brain-output/signals/daily_report.json`
Сформировано Python: `2026-06-05T08:12:13+00:00`
Модель: `probability-calibration-v0`
Таймфрейм для TradingView: `1h`

Цель: вручную сверить, что Pine на TradingView показывает тот же последний сигнал,
что Python runtime. Это контроль против расхождения Pine-детектора и проверенного Python.

Как проверять:
1. Открой тикер в TradingView.
2. Поставь таймфрейм из таблицы.
3. Убедись, что `Market mode = Stocks` для акций.
4. Сравни `Last signal`, `Pattern`, `P / EV`, `Entry`, `Stop`, `Target`.
5. `Action now` может стать `WAIT`, если Pine видит `TP passed`, `SL hit`, `STALE` или `late entry`.

## Свежие торговые сигналы

| Тикер | TF | Python entry_ts | Pattern | Python action | Ожидаемый Action now | P/EV | Entry | Stop | Target | Проверка |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| AVGO | 1h | 2026-06-04 15:30:00-04:00 | flat | buy | BUY, если в Pine статус ACTIVE и вход не late | 55.4% / +0.41% | 419.03 | 373.46 | 464.60 | сверить на графике |
| MSFT | 1h | 2026-06-04 09:30:00-04:00 | flat | buy | BUY, если в Pine статус ACTIVE и вход не late | 55.4% / +0.41% | 430.14 | 410.91 | 449.37 | сверить на графике |
| AMZN | 1h | 2026-06-04 09:30:00-04:00 | flat | buy | BUY, если в Pine статус ACTIVE и вход не late | 55.4% / +0.41% | 253.82 | 231.75 | 275.90 | сверить на графике |
| ORCL | 1h | 2026-06-04 09:30:00-04:00 | flat | buy | BUY, если в Pine статус ACTIVE и вход не late | 55.4% / +0.41% | 233.48 | 222.95 | 244.01 | сверить на графике |
| TSLA | 1h | 2026-06-03 10:30:00-04:00 | flat | buy | BUY, если в Pine статус ACTIVE и вход не late | 55.4% / +0.41% | 429.86 | 404.79 | 454.93 | сверить на графике |
| COST | 1h | 2026-06-04 13:30:00-04:00 | flat | sell | SELL, если в Pine статус ACTIVE и вход не late | 54.5% / +0.33% | 970.34 | 1014.18 | 926.49 | сверить на графике |
| NFLX | 1h | 2026-06-04 11:30:00-04:00 | flat | sell | SELL, если в Pine статус ACTIVE и вход не late | 54.5% / +0.33% | 81.82 | 82.06 | 81.58 | сверить на графике |

## Последние no-trade наблюдения

Эти строки не должны давать рабочий вход в Pine. Нормальный результат: `Action now = WAIT`.

| Тикер | TF | Python entry_ts | Pattern | Python action | Ожидаемый Action now | P/EV | Entry | Stop | Target | Проверка |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| AAPL | 1h | 2026-06-02 09:30:00-04:00 | triangle | skip | WAIT | 40.0% / -0.18% | 310.34 | n/a | n/a | должно быть WAIT/no-trade |
| AMAT | 1h | 2026-06-04 10:30:00-04:00 | triangle | skip | WAIT | 40.0% / -0.18% | 499.76 | n/a | n/a | должно быть WAIT/no-trade |
| AMD | 1h | 2026-06-04 09:30:00-04:00 | impulse | skip | WAIT | 50.2% / -0.17% | 516.28 | n/a | n/a | должно быть WAIT/no-trade |
| BKNG | 1h | 2026-06-04 09:30:00-04:00 | triangle | skip | WAIT | 40.0% / -0.18% | 169.84 | n/a | n/a | должно быть WAIT/no-trade |
| CRM | 1h | 2026-06-04 11:30:00-04:00 | impulse | skip | WAIT | 50.2% / -0.17% | 188.80 | n/a | n/a | должно быть WAIT/no-trade |
| GOOGL | 1h | 2026-06-04 09:30:00-04:00 | impulse | skip | WAIT | 48.0% / +0.22% | 368.19 | n/a | n/a | должно быть WAIT/no-trade |
| INTU | 1h | 2026-06-02 09:30:00-04:00 | triangle | skip | WAIT | 40.0% / -0.16% | 317.67 | n/a | n/a | должно быть WAIT/no-trade |
| ISRG | 1h | 2026-06-03 15:30:00-04:00 | impulse | skip | WAIT | 48.0% / +0.22% | 407.36 | n/a | n/a | должно быть WAIT/no-trade |
| JPM | 1h | 2026-06-03 13:30:00-04:00 | triangle | skip | WAIT | 40.0% / -0.18% | 301.83 | n/a | n/a | должно быть WAIT/no-trade |
| LLY | 1h | 2026-05-28 12:30:00-04:00 | impulse | skip | WAIT | 50.2% / -0.17% | 1122.34 | n/a | n/a | должно быть WAIT/no-trade |
| META | 1h | 2026-06-04 14:30:00-04:00 | triangle | skip | WAIT | 40.0% / -0.16% | 624.47 | n/a | n/a | должно быть WAIT/no-trade |
| NOW | 1h | 2026-06-02 09:30:00-04:00 | impulse | skip | WAIT | 50.2% / -0.17% | 124.60 | n/a | n/a | должно быть WAIT/no-trade |
| NVDA | 1h | 2026-06-01 09:30:00-04:00 | impulse | skip | WAIT | 48.0% / +0.22% | 221.37 | n/a | n/a | должно быть WAIT/no-trade |
| QCOM | 1h | 2026-06-03 10:30:00-04:00 | triangle | skip | WAIT | 40.0% / -0.18% | 249.69 | n/a | n/a | должно быть WAIT/no-trade |
| WMT | 1h | 2026-06-03 09:30:00-04:00 | impulse | skip | WAIT | 48.0% / +0.22% | 116.06 | n/a | n/a | должно быть WAIT/no-trade |

## Критерии прохождения

- `Pattern` совпадает с Python или расхождение занесено в backlog Pine parity.
- `Last signal` совпадает по стороне: `buy -> BUY`, `sell -> SELL`, `skip/wait -> WAIT`.
- `Entry`, `Stop`, `Target` отличаются только на округление цены.
- Для crypto при `Market mode = Stocks` Pine должен показывать `WAIT / unsupported market`.
