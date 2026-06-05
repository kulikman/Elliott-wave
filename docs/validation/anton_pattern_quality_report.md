# Anton pattern quality report

Цель: найти паттерны и таймфреймы, которые помогают Антону принимать решения `BUY / SELL / WAIT` на акциях.

Watchlist: `AAPL, MSFT, NVDA, AMZN, GOOGL, META, TSLA, AVGO, AMD, NFLX, COST, JPM, WMT, LLY, ORCL, CRM, QCOM, INTU, NOW, AMAT, BKNG, ISRG`
Исторических фигур: `17162` по `58` активам; TF: `15m, 1d, 1h, 1w, 30m, 4h`.
Фильтр отчёта: `22` акций watchlist: `2782` фигур.
TP/SL сделок sprint6: `4282` всего; по watchlist: `641`.
В TP/SL таблицах показаны только группы с `n >= 10`.

## Короткий вывод

- Рабочая торговая база остаётся прежней: `flat` и `double_corr` торгуются fade-направлением.
- `impulse` и `triangle` не должны давать вход: их роль в индикаторе — `WAIT / context`.
- По watchlist лучший подтверждённый TP/SL сигнал сейчас — `flat 1h long`: `TRADE small-size`, не агрессивный `all-in`.
- `double_corr` часто даёт лучший forward edge, но по watchlist TP/SL выборка мала; это сильный research-кандидат, не `A`-сигнал.
- `flat` даёт больше наблюдений и стабильнее подходит для ежедневного рабочего сигнала, но short-сторону нужно фильтровать.

## Лучшие forward-return комбинации по акциям watchlist

| Pattern | TF | Horizon | n | Hit | Mean | Sharpe-like | Conf | Decision |
|---|---|---:|---:|---:|---:|---:|---|---|
| flat | 1h | 10 | 129 | 58.9% | +0.61% | 0.23 | medium | TRADE fade |
| double_corr | 1h | 100 | 21 | 95.2% | +8.66% | 1.48 | low | RESEARCH |
| double_corr | 1h | 50 | 21 | 100.0% | +7.84% | 1.43 | low | RESEARCH |
| double_corr | 1h | 20 | 21 | 85.7% | +2.50% | 0.86 | low | RESEARCH |
| flat | 15m | 5 | 29 | 58.6% | +0.41% | 0.32 | low | RESEARCH |
| double_corr | 1h | 10 | 21 | 57.1% | +0.64% | 0.28 | low | RESEARCH |
| flat | 4h | 20 | 36 | 61.1% | +1.74% | 0.21 | low | RESEARCH |
| flat | 1d | 20 | 22 | 59.1% | +3.05% | 0.21 | low | RESEARCH |
| flat | 1h | 20 | 129 | 60.5% | +0.82% | 0.17 | medium | TRADE candidate |
| flat | 1h | 50 | 129 | 55.0% | +1.02% | 0.11 | medium | TRADE candidate |
| flat | 4h | 10 | 36 | 61.1% | +0.65% | 0.10 | low | RESEARCH |
| flat | 1w | 20 | 15 | 86.7% | +17.59% | 0.80 | low | RESEARCH |
| flat | 30m | 10 | 13 | 84.6% | +0.98% | 0.73 | low | RESEARCH |
| flat | 1w | 50 | 15 | 80.0% | +49.93% | 0.56 | low | RESEARCH |
| flat | 30m | 20 | 13 | 61.5% | +1.07% | 0.53 | low | RESEARCH |
| flat | 1w | 100 | 15 | 73.3% | +133.56% | 0.44 | low | RESEARCH |
| flat | 30m | 50 | 13 | 69.2% | +1.05% | 0.16 | low | RESEARCH |
| flat | 1w | 10 | 15 | 60.0% | +1.51% | 0.12 | low | RESEARCH |
| flat | 1w | 5 | 15 | 66.7% | +1.55% | 0.11 | low | RESEARCH |
| flat | 30m | 100 | 13 | 53.8% | +0.89% | 0.11 | low | RESEARCH |
| flat | 4h | 5 | 36 | 58.3% | +0.39% | 0.09 | low | RESEARCH |
| flat | 1d | 10 | 22 | 54.5% | +0.83% | 0.09 | low | RESEARCH |
| flat | 15m | 20 | 29 | 51.7% | +0.18% | 0.08 | low | RESEARCH |
| flat | 30m | 5 | 13 | 61.5% | +0.06% | 0.06 | low | RESEARCH |
| flat | 1d | 50 | 22 | 54.5% | +1.58% | 0.06 | low | RESEARCH |

## TP/SL качество по акциям watchlist

| Pattern | TF | Side | n | Win | EV | Sharpe-like | Portfolio Sharpe | DD | Conf | Decision |
|---|---|---|---:|---:|---:|---:|---:|---:|---|---|
| flat | 1h | long | 45 | 68.9% | +1.52% | 0.58 | 1.61 | -1.7% | low | TRADE small-size |
| impulse | 1h | short | 13 | 53.8% | +0.02% | 0.01 | -0.29 | -0.9% | low | WAIT |
| triangle | 1h | short | 186 | 50.0% | +0.16% | 0.06 | 0.18 | -9.7% | high | WAIT |
| flat | 1h | short | 34 | 47.1% | +0.03% | 0.01 | -0.07 | -4.3% | low | WAIT |
| impulse | 1h | long | 16 | 43.8% | -0.01% | -0.00 | -0.34 | -1.4% | low | WAIT |
| triangle | 1d | short | 35 | 40.0% | -1.54% | -0.21 | -0.34 | -6.3% | low | WAIT |
| triangle | 1h | long | 244 | 46.3% | -0.11% | -0.05 | -0.63 | -15.4% | high | WAIT |
| triangle | 1d | long | 40 | 35.0% | -1.85% | -0.25 | -0.65 | -9.9% | low | WAIT |

## TP/SL reference по всем 58 активам

Эта таблица нужна для калибровки индикатора, но решение по деньгам Антона должно учитывать watchlist-таблицу выше.

| Pattern | TF | Side | n | Win | EV | Sharpe-like | Portfolio Sharpe | DD | Conf | Decision |
|---|---|---|---:|---:|---:|---:|---:|---:|---|---|
| flat | 1h | long | 251 | 55.4% | +0.41% | 0.21 | 1.29 | -4.9% | high | TRADE small-size |
| flat | 1d | long | 24 | 66.7% | +2.19% | 0.22 | 0.77 | -2.7% | low | RESEARCH |
| flat | 1d | short | 23 | 69.6% | +4.51% | 0.44 | 0.42 | -2.6% | low | RESEARCH |
| double_corr | 1h | short | 15 | 86.7% | +1.83% | 0.71 | 0.99 | -1.1% | low | RESEARCH |
| flat | 1h | short | 233 | 54.5% | +0.33% | 0.15 | 0.89 | -6.9% | high | RESEARCH |
| double_corr | 1h | long | 14 | 78.6% | +0.83% | 0.36 | 0.71 | -1.1% | low | RESEARCH |

## All-TF тест на крупных ликвидных акциях

Источник: `docs/validation/top_stocks_multitf_decision_test.md`, generated `2026-06-05T10:01:02+00:00`.
Universe: `NVDA, AAPL, GOOGL, MSFT, AMZN, AVGO, TSLA, META, JPM, BRK-B, LLY, V, MA, NFLX, XOM, WMT, COST, UNH, ORCL, HD`.
Сделочных строк: `14680`, базовых сигналов: `7812`.

### Лучшие строки Flat/DoubleCorr

| Pattern | TF | Mode | MTF | n | Win | Mean | PF | Sharpe-trade | TP | SL | Avg bars |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| flat | 4h | fade | none | 41 | 63.4% | +1.69% | 3.43 | 6.69 | 39.0% | 19.5% | 13.02 |
| flat | 1h | fade | figure_with_htf | 110 | 55.5% | +0.55% | 1.87 | 3.64 | 35.5% | 26.4% | 13.07 |
| flat | 1h | fade | none | 182 | 55.5% | +0.50% | 1.63 | 2.76 | 29.7% | 23.6% | 14.36 |
| flat | 15m | fade | figure_with_htf | 32 | 56.2% | +0.16% | 1.89 | 3.78 | 37.5% | 28.1% | 10.91 |
| flat | 15m | fade | none | 53 | 58.5% | +0.16% | 1.53 | 2.37 | 26.4% | 22.6% | 13.42 |
| flat | 1h | fade | trade_not_against_htf | 72 | 55.6% | +0.43% | 1.40 | 1.95 | 20.8% | 19.4% | 16.33 |

### Портфельные варианты

| Variant | n | CAGR | Sharpe | DD | Calmar | Win | Final |
|---|---:|---:|---:|---:|---:|---:|---:|
| Flat+DC fade all TF / no HTF | 395 | 9.2% | 1.63 | -4.6% | 1.99 | 64.3% | $220,687 |
| Flat+DC fade all TF / Pine HTF not-against | 192 | 5.3% | 1.29 | -3.2% | 1.67 | 70.3% | $158,395 |
| Flat+DC fade all TF / old figure-with-HTF | 203 | 4.9% | 1.12 | -4.4% | 1.12 | 58.6% | $139,525 |
| Flat+DC fade 1h+4h+1d / no HTF | 286 | 12.4% | 1.84 | -4.6% | 2.67 | 63.3% | $174,792 |
| DoubleCorr fade 1h+4h / no HTF | 32 | 8.6% | 2.51 | -0.3% | 25.43 | 96.9% | $124,873 |
| Flat fade 1h+1d / no HTF | 207 | 4.2% | 0.78 | -11.2% | 0.38 | 57.0% | $121,841 |

All-TF вывод: лучший баланс сейчас у `Flat+DC fade 1h+4h+1d / no HTF`; жёсткий Pine HTF-фильтр снижает доходность, хотя повышает win-rate.


## Что считать идеальным паттерном для v0

1. `flat 1h/4h fade`: основной практический класс сигналов; `flat 1h long` лучший по watchlist, `flat 4h fade` лучший в all-TF тесте.
2. `flat 1h short`: не самостоятельный идеальный сигнал по watchlist; нужен дополнительный фильтр тренда/MTF или `WAIT`.
3. `double_corr 1h/4h fade`: сильный кандидат с хорошим портфельным поведением, но показывать с пониженной confidence из-за малого `N`.
4. `flat 1d/4h`: использовать как старший контекст и более спокойный setup, не как шумный частый сигнал.
5. `15m/30m`: research/scalping зона; по умолчанию не включать на графике Антона, чтобы убрать шум.
6. `impulse` и `triangle`: не торговать в v0, использовать только как причину `WAIT`.

## Правило для индикатора Антона

- `BUY`: fresh `flat/double_corr` fade long, не late, поддержанный risk/reward и market mode; strongest now: `flat 1h long`.
- `SELL`: fresh `flat/double_corr` fade short только с дополнительным фильтром качества; иначе `WAIT`.
- `WAIT`: target passed, stop hit, stale, late entry, unsupported market, `impulse`, `triangle`, либо низкое качество группы.
- `EXIT`: target = полный ретрейс/цель фигуры; stop = амплитуда фигуры; после прохождения target вход запрещён.

## Следующий шаг

Перевести MTF в score/penalty-фильтр и повторить отчёт: старший TF должен снижать confidence, но не быть жёстким блоком по умолчанию.
