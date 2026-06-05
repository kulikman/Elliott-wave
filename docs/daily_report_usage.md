# Daily Probability Report

Основной файл для Антона:

- `brain-output/signals/daily_report.md`

Он показывает свежие сигналы по watchlist в формате:

`Акция | Действие | Фигура | Время сигнала | P(win) | EV | Уверенность | Вход | Стоп | Цель`

## Настройка watchlist

Файл:

- `configs/watchlist.yaml`

Поля:

- `tickers` — список тикеров.
- `interval` — таймфрейм, например `1h` или `1d`.
- `actions` — какие действия показывать, обычно `buy` и `sell`.
- `fresh_hours` — сколько последних часов считать свежими.
- `limit` — максимум строк в отчёте.

## Ручной запуск

Из корня проекта:

```bash
python3 python/scripts/daily_report.py
```

Или через shell-wrapper с логом:

```bash
scripts/run_daily_report.sh
```

Лог:

- `brain-output/signals/logs/daily_report.log`

## Автозапуск через macOS launchd

Шаблон:

- `scripts/com.anton.elliott-wave.daily-report.plist`

По умолчанию настроен запуск каждый день в `09:45` локального времени macOS.

Установить:

```bash
scripts/install_daily_report_launchd.sh
```

Проверить:

```bash
launchctl list | grep elliott-wave
```

Отключить:

```bash
scripts/uninstall_daily_report_launchd.sh
```

## Важное ограничение

Это research-сигнал Probability Model v0, а не финансовая гарантия. Перед реальной сделкой Антон должен проверить график, ликвидность, новости, общий рынок и размер риска.
