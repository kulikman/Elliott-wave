# wave_books_pool_2 sprint plan

Рабочий план для отдельного пула `wave_books_pool_2`. Цель: сохранить пул независимым, извлекать AKU без смешивания типов и источников, затем подготовить кандидатов для возможного объединения с первым пулом.

## Sprint 0 — методологическая чистка

Цель: исправить слабые места первого прохода и закрепить правила дальнейшей работы.

- Переклассифицировать `AKU-0253` из `definition` в `heuristic`.
- Оставить `AKU-0248`-`AKU-0252` как draft definitions-кандидаты.
- Не формализовать ничего до human review.
- Зафиксировать правило: один урок, один тип AKU, максимум 10 AKU за проход.
- Проверка: `python3 tools/validate_aku.py`, `python3 -m pytest`.

## Sprint 1 — definitions по одному уроку

Цель: добрать чистые определения, не смешивая уроки.

- `intraday-l01-three-touches`: правило/термин третьего касания, если есть явное определение. Статус: явного definition нет, перенесено в rules/heuristics.
- `intraday-l02-positive-lock`: положительный замок. Статус: создан `AKU-0254`.
- `intraday-l06-ellipses`: эллипс, дуга ВАЛа, сердце фрактала. Статус: создан `AKU-0255` для эллипсов как обрамления зигзага Нили.
- `intraday-l08-fractal-dimension-shift`: фрактал, мерность, смена мерности. Статус: создан `AKU-0256` для смены мерности фрактала.
- Повторно проверить `AKU-0248`-`AKU-0252` после human review.
- Gate: все новые AKU имеют `verbatim_quote`, `status: draft`, `formalization.status: not_attempted`.

## Sprint 2 — conditional_rules

Цель: извлечь правила вида "если/при/когда" с числами и условиями.

- `intraday-l03-s-curves`: 100% откат S-ки, S-ка у поддержки/сопротивления/линии прорыва, S-ка против тренда.
  Статус: созданы `AKU-0257`-`AKU-0260` по откатам S-ки.
- `intraday-l04-stella`: откат 81% и более, два вида откатов, терминальный вариант.
  Статус: создан `AKU-0261` по условию "если Стэлла видна как коррекция по ходу тренда"; уровни 61%/81%/>81% оставлены как Vision-кандидаты до human review.
- `intraday-l05-val`: 3 касания ВАЛа, сильный откат у поддержки/сопротивления, завершение тренда.
  Статус: созданы `AKU-0262`-`AKU-0264`; терминальный 100% откат оставлен как Vision-кандидат до human review.
- `intraday-l07-moving-correction`: 161.8% после подвижной коррекции, 61.8% для волны `c`.
  Статус: созданы `AKU-0265`-`AKU-0267` по Vision-тексту страницы 22; все требуют human review.
- `intraday-l10-trading-technique`: стоп 8-10 пунктов от фрактала/фигуры ВА.
  Статус: создан `AKU-0268` по ложному движению на новости; общий стоп и новостная волна II/III перенесены в Sprint 3 heuristics.
- Gate: ни одно числовое правило не создаётся без дословной цитаты.

## Sprint 3 — heuristics

Цель: прикладные торговые эвристики, которые не являются строгими правилами.

- Входы, доливки, короткие тейк-профиты, перевод в безубыток.
- Торговля каждой различимой M1-волны.
- Новости как волна II/III и расчёт новостной импульсной волны.
- Практическое использование эллипсов, ВАЛов, Стэлл и S-ок для входов.
- Gate: всё с языком "часто", "чаще всего", "лучше", "может" остаётся `strength: heuristic`.

Статус:

- `intraday-l01-three-touches`: созданы `AKU-0299`-`AKU-0300` по завершению тренда на третьем касании и разворотному сценарию на линии прорыва.
- `intraday-l10-trading-technique`: созданы `AKU-0269`-`AKU-0271` по стопу 8-10 пунктов, новостной волне II/III и фрактальному серфингу.
- `intraday-l02-positive-lock`: созданы `AKU-0272`-`AKU-0275` по M1-M5 для замка, нескольким сделкам после фигуры роста, переводу лучшей сделки в БУ и попеременному добавлению сделок сверху/снизу.
- `intraday-l03-s-curves`: созданы `AKU-0276`-`AKU-0278` по входу на подволнe S-ки по тренду, наложению S-ки на импульс с растянутой 3-й и точности сделок через структуру/откат S-ки.
- `intraday-l04-stella`: создан `AKU-0279` по открытию сделок в самом начале Стэллы на основе знания её волновой структуры; конкретные схемы входа по картинкам перенесены в Vision gap.
- `intraday-l05-val`: созданы `AKU-0280`-`AKU-0281` по торговле последней волны ВАЛа, когда не хватает 3-го касания, и торговле второй волны ВАЛа после сценария завершения на 2-м касании.
- `intraday-l06-ellipses`: созданы `AKU-0282`-`AKU-0285` по точным входам через C=A в зигзаге, точности входа у линий, эллипсу как завершению крупной фигуры и фрактальному прогнозу на 2-3 шага.
- `intraday-l07-moving-correction`: созданы `AKU-0286`-`AKU-0291` по доливке на подвижной коррекции, входу в конце подвижной плоской коррекции, входу в волну C, входу у линии прорыва, комбинации для точного входа и разворотной сделке по окончанию эллипса.
- `intraday-l08-fractal-dimension-shift`: созданы `AKU-0292`-`AKU-0294` по фракталам через границы эллипсов, точке смены мерности как месту входа и расчёту точки смены мерности для прогноза разворота.
- `intraday-l09-growth-formulas`: созданы `AKU-0295`-`AKU-0298` по PTV/PVT на одном энергетическом уровне, PTV-треугольнику как прогнозному инструменту, корню из 3 для нового уровня мерности и прогнозу разворотной цены/времени.
- Итог: текстовый heuristic-проход Sprint 3 покрывает все уроки 1-10; визуальные схемы входов остаются в Sprint 5.

## Sprint 4 — exceptions

Цель: выделить исключения и конфликтные случаи.

- S-ка по ходу тренда с откатом 50% и менее.
- S-ка в конце тренда с откатом более 100%, "Черный Лебедь".
- Ложное движение на новости.
- Случаи, где терминальный вариант отличается от обычного импульса.
- Gate: если исключение не ссылается на базовое правило, оно остаётся `requires_review: true`.

Статус:

- `intraday-l03-s-curves`: созданы `AKU-0301`-`AKU-0302` по S-ке по ходу тренда с откатом 50% и менее и S-ке в конце тренда/"Черному Лебедю" с откатом более 100%.
- `intraday-l10-trading-technique`: создан `AKU-0303` по ложному движению на новости и стопу дальше обычного.
- `intraday-l04-stella`: создан `AKU-0304` по допустимому перекрытию волн 2 и 4 в терминальном импульсе в растянутой 5-й.
- `intraday-l05-val`: создан `AKU-0305` по перекрытию волн 2 и 4 в терминальном импульсе с растянутой 1-й.
- Связи с базовыми правилами внесены через `related_aku`; `contradicts_aku` оставлен пустым до human review.

## Sprint 5 — Vision gap pass

Цель: закрыть визуальные пробелы перед human review.

- `intraday-l01-three-touches`: страницы/картинки с третьим касанием.
- `intraday-l02-positive-lock`: схемы замка и управления сделками.
- `intraday-l06-ellipses`: построение эллипса, C=A, плоская коррекция в центре.
- `intraday-l08-fractal-dimension-shift`: повторить страницу 30 и проверить L-пропорции.
- `intraday-l09-growth-formulas`: страницы 62-75 с коэффициентами, π и золотой пропорцией.
- Gate: Vision-основанные AKU остаются `requires_review: true` до проверки человеком.

Статус:

- Sprint 5 начат как triage-pass, без создания новых AKU.
- `intraday-l01-three-touches`: создан `vision-notes.md` по страницам 2-3 и 18-25; кандидаты по третьему касанию остаются `requires_review`.
- `intraday-l02-positive-lock`: создан `vision-notes.md` по страницам 2-5 и 26-27; кандидаты по алгоритму лока, БУ и стопам остаются `requires_review`.
- `intraday-l06-ellipses`: Vision-заметки есть, но построение эллипса и критерии идентификации пока слишком визуальны для нового AKU без human review.
- `intraday-l08-fractal-dimension-shift`: создан отдельный `vision-notes-page-030.md`; страница 30 закрыта как Vision gap, но терминальная структура и варианты коррекций остаются `requires_review`.
- `intraday-l09-growth-formulas`: страницы 62-75 закрыты отдельными Vision-файлами; страницы 68 и 75 добраны точечно после обрыва пакетных ответов.
- Следующий безопасный шаг: сформировать Sprint 6 human review queue по всем `requires_review` и визуальным кандидатам, без автоматической формализации.

## Sprint 6 — human review queue

Цель: подготовить очередь для проверки Антоном.

- Сгруппировать AKU по урокам и типам.
- Отдельно вынести `requires_review: true`.
- Отдельно вынести потенциальные связи с первым пулом Нили.
- После проверки менять `status: draft` только вручную человеком.

Статус:

- Создана очередь `docs/pool_2_human_review_queue.md`.
- Сгруппированы 54 pool 2 AKU с `requires_review: true`.
- Отдельно вынесен visual-only слой для ручной проверки картинок и Vision-выводов.
- AKU-статусы и формализация не менялись.
- Следующий безопасный шаг: Sprint 7 merge candidates — подготовить связи с первым пулом без автоматического объединения.

## Sprint 7 — merge candidates

Цель: подготовить, но не выполнить объединение с первым пулом.

- Сопоставить S-ку, Стэллу и ВАЛ с существующими AKU по `impulse-extension`.
- Сопоставить подвижную коррекцию с `flat`/running flat AKU.
- Сопоставить PTV/мерность только как авторскую эвристику, не как правило Нили.
- Создать список `related_aku` кандидатов, но не заполнять связи без human approval.

Статус:

- Создан `docs/pool_2_merge_candidates.md`.
- Зафиксированы high/medium/low-confidence связи с первым пулом.
- `related_aku`, `extends_aku`, `contradicts_aku` в AKU YAML не менялись.
- Следующий безопасный шаг: дождаться human review по `docs/pool_2_human_review_queue.md` и `docs/pool_2_merge_candidates.md`.

## Sprint 8 — overlay architecture

Цель: зафиксировать решение "отдельный overlay сейчас, возможный единый интерфейс позже".

- Pool 2 развивать как отдельный overlay-модуль поверх Neely Core.
- Neely Core не загрязнять торговыми эвристиками, PTV/π/√3 и positive lock.
- В финальном TradingView можно сделать единый индикатор с режимами, но внутренние слои должны быть разделены.
- Gate: не генерировать `spec_vN.json` для pool 2 до human review.

Статус:

- Создан `brain-output/indicator-spec/pool2-overlay-architecture.md`.
- Зафиксированы модули: S-ка, Стэлла, ВАЛ, Ellipse, Moving Correction, Experimental PTV, Trade Management.
- Следующий безопасный шаг: после human review подготовить `pool2_overlay_spec_draft.json` только из принятых high-confidence кандидатов.

## Sprint 9 — overlay implementation backlog

Цель: подготовить практический план реализации без создания исполнимого pool 2 spec до review.

- Привязать overlay к текущим кодовым якорям: `python/ewb/figures.py`, `python/ewb/confirm.py`, `pine/ewb_monowaves_mtf.pine`, `pine/ewb_confirm.pine`.
- Сначала Python research prototype, потом Pine перенос.
- Разделить structural overlay, visual geometry, experimental PTV и trade management.
- Gate: no core override — pool 2 сигналы не меняют типы и валидность фигур Neely Core.

Статус:

- Создан `brain-output/indicator-spec/pool2-overlay-backlog.md`.
- Следующий безопасный шаг: дождаться human review или подготовить шаблон review-decision файла для Антона.

## Sprint 10 — review decisions file

Цель: подготовить безопасный файл решений до любых изменений AKU YAML.

- Отдельно хранить решения Антона по AKU, visual-only пунктам, merge candidates и implementation gates.
- Не использовать `tools/review_session.py` до заполнения/проверки этого файла, потому что инструмент сразу меняет AKU-статусы.
- Gate: файл решений не применяется автоматически.

Статус:

- Создан `docs/pool_2_review_decisions.yaml`.
- Все 54 `requires_review` AKU внесены как `pending`.
- Implementation gates для Python/Pine overlay оставлены заблокированными до human review.

## Sprint 11 — probability model v0

Цель: перевести индикатор из режима "разметить волны" в режим "оценить вероятность движения и торговое решение".

- Зафиксировать контракт вероятностного выхода: `p_up`, `p_down`, `p_trade_win`, `expected_net_return`, `confidence`, `sample_size`, `recommended_action`, entry/stop/target.
- Разделить финальную стратегию `sprint6-final.md` и сырой профиль сделок `trades_sprint6.parquet`.
- Использовать `flat` и `double_corr` как единственные trade-сигналы v0.
- Оставить `impulse` и `triangle` как `skip` до появления положительного edge.
- Gate: Pool 2 overlay включается в торговый сигнал только если улучшает вероятность, ожидаемую доходность или drawdown.

Статус:

- Создан `brain-output/indicator-spec/probability-model-v0.md`.
- Созданы машинно-читаемая и human-readable калибровки: `brain-output/indicator-spec/probability_calibration_v0.json` и `brain-output/indicator-spec/probability_calibration_v0.md`.
- Добавлен скрипт генерации `python/scripts/build_probability_calibration.py`.
- Добавлен shared-модуль `python/ewb/research/probability.py` и тесты probability contract.
- Базовая стратегия v0: `flat`/`double_corr` fade direction, без HTF-фильтра.
- Из `sprint6-final.md`: 1061 сделка, CAGR 41.0%, Sharpe 2.82, Max DD -7.1%, win rate 61.0%.
- По типам в финальной стратегии: `flat` — 941 сделка, win 56.6%; `double_corr` — 120 сделок, win 95.0%.
- Сырой calibration source даёт 36 строк lookup по уровням `fig_type+interval+side`, `fig_type+interval`, `fig_type+side`, `fig_type`.
- Следующий безопасный шаг: встроить lookup в signal contract и затем проверять Pool 2 признаки как улучшатели `p_up/p_down`, `p_trade_win` и `expected_net_return`.

## Sprint 12 — probability signal contract runtime

Цель: превратить калибровочную таблицу в минимальный рабочий сигнал для будущего Pine/алертов.

- На вход: `fig_type`, `interval`, `direction`, подтверждённая точка входа и амплитуда фигуры.
- Рассчитать side через fade: `direction=up -> short`, `direction=down -> long`.
- Найти probability row по lookup priority.
- Вернуть `recommended_action`, `p_up`, `p_down`, `p_trade_win`, `expected_net_return`, `confidence`, `sample_size`, entry/stop/target.
- Gate: если `fig_type` не `flat`/`double_corr`, возвращать `skip`, даже если визуальный overlay красивый.

Статус:

- Реализован runtime contract в `python/ewb/research/probability.py`: `build_probability_signal`, `lookup_probability_row`, `fade_side`, `price_levels`.
- Добавлен CLI `python/scripts/probability_signal.py` для проверки одного сигнала по calibration JSON.
- Добавлен сканер `python/scripts/scan_probability_signals.py`: download OHLC -> monowaves -> figures -> probability signals.
- Добавлены тесты на lookup priority, fade side, risk box и запрет торговых уровней для `skip`.
- Добавлен адаптер `probability_signal_from_figure`, который берёт entry на `pivots[-1].confirmation_idx`, а не на экстремуме.
- Пример: `flat`, `1h`, `direction=down`, `entry=100`, `amplitude=4` возвращает `buy`, P(win) 55.4%, confidence high, stop 96, target 104.
- Пример: `triangle`, `1h`, `direction=up` возвращает `skip` и не выдаёт stop/target.
- Реальный smoke-test: `AAPL 1h` последние свежие сигналы возвращают `skip`; фильтр `--actions buy,sell` находит последние actionable `flat` сигналы в истории.
- Batch-output реализован через `--save`: сканер сохраняет JSON и Markdown в `brain-output/signals/`.
- Созданы `brain-output/signals/probability_signals_1h_buy-sell.json` и `brain-output/signals/probability_signals_1h_buy-sell.md` для watchlist `AAPL,MSFT`.
- В сохранённом smoke-test самый свежий actionable сигнал: `MSFT`, `buy`, `flat`, `2026-06-04 09:30:00-04:00`, P(win) 55.4%, EV +0.41%, confidence high.
- Freshness-filter реализован: `--fresh-hours` и `--fresh-days`.
- Созданы `brain-output/signals/probability_signals_1h_buy-sell_fresh-48h.json` и `brain-output/signals/probability_signals_1h_buy-sell_fresh-48h.md`.
- Fresh smoke-test `AAPL,MSFT`, `1h`, `buy/sell`, `48h`: 1 свежий сигнал — `MSFT buy flat` от `2026-06-04 09:30:00-04:00`.
- Watchlist вынесен в `configs/watchlist.yaml`.
- Добавлен режим daily report: `python/scripts/daily_report.py`.
- Созданы стабильные пользовательские файлы `brain-output/signals/daily_report.md` и `brain-output/signals/daily_report.json`.
- `daily_report.md` русифицирован: `Акция`, `Действие`, `Фигура`, `P(win)`, `EV`, `Уверенность`, `Вход`, `Стоп`, `Цель`.
- Добавлен wrapper `scripts/run_daily_report.sh`, который запускает daily report и пишет лог в `brain-output/signals/logs/daily_report.log`.
- Добавлен launchd-шаблон `scripts/com.anton.elliott-wave.daily-report.plist` для ежедневного запуска в `09:45`.
- Добавлены `scripts/install_daily_report_launchd.sh` и `scripts/uninstall_daily_report_launchd.sh`.
- Добавлена инструкция `docs/daily_report_usage.md`.
- Автозапуск включён через `scripts/install_daily_report_launchd.sh`; `launchctl list` видит `com.anton.elliott-wave.daily-report`.
- Telegram-канал пропущен по решению Антона.
- `scripts/run_daily_report.sh` снова делает только локальный daily report.
- Следующий безопасный шаг: улучшить локальный daily report или перейти к Pine/TradingView переносу сигнала.
