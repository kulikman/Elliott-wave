# EWB Local Dashboard

Локальный сайт показывает рабочую систему вокруг индикатора:

- текущие сигналы watchlist;
- открытые forward-сделки;
- историю закрытых сделок;
- сравнение historical baseline vs forward;
- решение `OBSERVE / PAPER ONLY / BLOCK / READY TO REVIEW`.

## Запуск

```bash
python3 python/scripts/run_dashboard.py
```

Открыть:

```text
http://127.0.0.1:8765
```

## Страницы

- `Dashboard` — главное состояние системы и кнопка запуска pipeline.
- `Action Board` — главный рабочий экран: решение, тикер, сторона, TF, структура, P, R:R, уровни, свежесть и ссылка на TradingView.
- `Signals` — свежие сигналы из `brain-output/signals/daily_report.json`, ручное добавление alert и лента пришедших alert.
- `Trades` — открытые сделки из forward-журнала.
- `History` — закрытые forward-сделки.
- `Trade Detail` — карточка одного сигнала/сделки, закрытие позиции и заметки Антона.
- `Backtest` — сравнение baseline и forward.
- `Settings` — профили watchlist, сохранение текущего режима и запуск scan.
- `Risk Settings` — размер счета, риск на сделку, максимальный размер позиции.

## TradingView webhook

Локальный endpoint:

```text
POST http://127.0.0.1:8765/api/alerts/tradingview
```

Пример payload:

```json
{
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
}
```

Важно: TradingView Cloud не сможет напрямую достучаться до `127.0.0.1`. Для реального webhook нужен публичный туннель или сервер. Для локальной проверки используй форму `Signals -> Add Alert` или `curl` на локальный endpoint.

## Источники данных

- `python/data/forward_signals/ewb_forward_events.jsonl`
- `brain-output/backtests/ewb_strategy_backtest_summary.json`
- `brain-output/backtests/ewb_forward_daily_report.json`
- `brain-output/signals/daily_report.json`
- `configs/watchlist.yaml`

## Журнал сделки

В таблицах `Alerts Feed`, `Trades` и `History` ID сигнала кликабельный. Карточка сделки показывает:

- исходный alert contract;
- entry / stop / target;
- R:R и свежесть сигнала;
- расчет позиции: quantity, капитал, риск и потенциальная прибыль;
- checklist перед входом;
- HTF context;
- outcome после закрытия;
- заметки Антона.

## Как Антону пользоваться

1. Открыть `Settings` и выбрать профиль: `Long-term`, `Swing`, `Intraday`, `Crypto` или `Anton Favorites`.
2. Нажать `Run scan for active watchlist`.
3. Открыть `Action Board`.
4. Смотреть только строки `REVIEW` и открытые сделки `HOLD`.
5. По `TV` открыть график TradingView и проверить волновую структуру/HTF.
6. Если сигнал подходит для paper trading, нажать `Paper`; сайт создаст сделку и откроет карточку.
7. Входить только если R:R >= 1, вероятность проходит фильтр, сигнал не старый и нет новостного риска.
8. После выхода закрыть сделку и добавить заметку.

## Watchlist профили

Профили хранятся в:

- `configs/watchlist_profiles.yaml`

Активный watchlist, который читает scanner:

- `configs/watchlist.yaml`

## Risk management

Настройки риска хранятся в:

- `configs/risk_settings.yaml`

Поля:

- `account_size` — размер счета.
- `risk_pct` — риск на одну сделку в процентах от счета.
- `max_position_pct` — максимум капитала в одной позиции.
- `currency` — валюта отображения.

Action Board показывает `Qty` и `Risk` по каждому сигналу. Карточка сделки показывает полный `Risk Plan`: размер позиции, капитал, риск, потенциальная прибыль и R:R.

Кнопка `Apply` копирует профиль в активный watchlist. Форма `Save active` сохраняет текущий список как профиль и сразу делает его активным.

Заметки пишутся в тот же JSONL-журнал как immutable event:

```json
{
  "event_type": "note",
  "signal_id": "...",
  "tag": "late_entry",
  "author": "anton",
  "note": "Вошел после движения 40% к TP"
}
```

Базовые теги: `note`, `late_entry`, `ignored_htf`, `moved_stop`, `manual_exit`, `news_risk`, `good_execution`.

## Следующие улучшения

- Equity curve и графики просадки.
- Фильтры по структурам волн и отдельные пресеты min P / min R:R.
