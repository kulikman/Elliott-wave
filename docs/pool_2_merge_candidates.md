# wave_books_pool_2 merge candidates

Кандидаты на будущую связку `wave_books_pool_2` с первым пулом Нили. Это не объединение и не изменение `related_aku`: документ фиксирует только гипотезы для ручной проверки.

## Gate

- Не менять `aku/*/AKU-*.yaml` автоматически.
- Не добавлять `related_aku`, `extends_aku`, `contradicts_aku` без human approval.
- Не повышать `status` и не запускать formalization.
- Pool 2 торговые эвристики связывать с Нили только как прикладной слой, если источник явно использует фигуры Нили.
- PTV/π/√3 считать авторской геометрической эвристикой, а не правилом Нили, пока не найден прямой первичный источник.

## High-confidence candidates

| Pool 2 source / AKU | Candidate first-pool AKU | Relation | Reason |
| --- | --- | --- | --- |
| `intraday-l03-s-curves`, `AKU-0248`, `AKU-0277` | `AKU-0200`, `AKU-0033` | `related_aku` candidate | S-ка прямо описана как обрамление импульса с растянутой 3-й волной; `AKU-0200` фиксирует растянутую 3-ю как распространённый случай, `AKU-0033` описывает постэффект импульса с растянутой 3-й. |
| `intraday-l04-stella`, `AKU-0249`, `AKU-0304` | `AKU-0049`, `AKU-0201`, `AKU-0034`, `AKU-0219`, `AKU-0010`, `AKU-0163`, `AKU-0220` | `related_aku` / possible `exception-context` | Стэлла связана с импульсом с растянутой 5-й; терминальный вариант требует сопоставления с обязательным перекрытием терминала и постэффектом терминального импульса. |
| `intraday-l05-val`, `AKU-0250`, `AKU-0305` | `AKU-0048`, `AKU-0080`, `AKU-0087`, `AKU-0032`, `AKU-0010`, `AKU-0163`, `AKU-0220` | `related_aku` / possible `exception-context` | ВАЛ связан с импульсом с растянутой 1-й; терминальный вариант ВАЛа связан с правилами терминального импульса и перекрытием волн 2/4. |
| `intraday-l07-moving-correction`, `AKU-0251`, `AKU-0265`, `AKU-0266`, `AKU-0267` | `AKU-0095`, `AKU-0213`, `AKU-0217`, `AKU-0243`, `AKU-0025`, `AKU-0026` | `related_aku` candidate | Подвижная/ползущая коррекция прямо совпадает с moving/running flat зоной: постэффект должен быть сильным, а следующая волна часто связана с растянутой волной. |
| `intraday-l06-ellipses`, `AKU-0255`, `AKU-0282` | `AKU-0160`, `AKU-0014`, `AKU-0015`, `AKU-0016`, `AKU-0024`, `AKU-0166` | `related_aku` candidate | Эллипс описан как обрамление зигзага Нили; C=A остаётся авторской торговой эвристикой, а базовая структура зигзага и проверки импульс/зигзаг есть в первом пуле. |

## Medium-confidence candidates

| Pool 2 source / AKU | Candidate first-pool AKU | Relation | Reason |
| --- | --- | --- | --- |
| `intraday-l01-three-touches`, `AKU-0299`, `AKU-0300` | `AKU-0052`, `AKU-0055`, `AKU-0036`, `AKU-0037` | weak `related_aku` candidate | Правило 3-х касаний авторское; возможная связь только через линии/касания коррекций и подтверждение после flat/zigzag. Не считать правилом Нили. |
| `intraday-l06-ellipses`, `AKU-0283`, `AKU-0284`, `AKU-0285` | `AKU-0036`, `AKU-0037`, `AKU-0160`, `AKU-0161`, `AKU-0163` | weak `related_aku` candidate | Линия прорыва и окончание эллипса могут соответствовать пост-подтверждениям коррекций/терминала, но критерии построения эллипса визуальные. |
| `intraday-l08-fractal-dimension-shift`, `AKU-0256`, `AKU-0292`, `AKU-0293`, `AKU-0294` | `AKU-0003`, `AKU-0013`, `AKU-0042`, `AKU-0043` | conceptual `related_aku` candidate | Смена мерности фрактала может быть связана с degree/similarity/balance, но язык pool 2 фрактальный и авторский; прямого правила Нили нет. |
| `intraday-l10-trading-technique`, `AKU-0268`, `AKU-0269`, `AKU-0270`, `AKU-0303` | `AKU-0032`, `AKU-0033`, `AKU-0034`, `AKU-0219`, `AKU-0220` | trading-layer relation | Стопы и новости являются прикладным риск-слоем поверх ожидаемых постэффектов импульсов/терминалов. Не переносить в правила Нили. |

## Low-confidence / do not merge yet

| Pool 2 source / AKU | Candidate first-pool AKU | Reason |
| --- | --- | --- |
| `intraday-l09-growth-formulas`, `AKU-0252`, `AKU-0295`-`AKU-0298` | `AKU-0003`, possibly degree/time rules | PTV, π, √2/√3/√5 и формулы роста являются авторской геометрической моделью. Связь с Нили допустима только как conceptual note о price/time/degree, не как rule merge. |
| `intraday-l02-positive-lock`, `AKU-0254`, `AKU-0272`-`AKU-0275` | none / trading management only | Положительный замок — управление позициями. Связь с первым пулом только через внешние сигналы входа, но сами правила buy/sell/БУ/стоп не являются NeoWave. |
| `intraday-l03-s-curves`, `AKU-0257`-`AKU-0260`, `AKU-0301`, `AKU-0302` | `AKU-0219`, correction posteffect AKU | Откаты S-ки 50/100/>100% могут конфликтовать или пересекаться с постэффектами импульсов, но сначала нужно подтвердить, является ли S-ка именно импульсом, коррекцией или визуальным обрамлением. |

## Suggested human decisions

### Accept as related candidates after review

- `AKU-0248` -> `AKU-0200`, `AKU-0033`
- `AKU-0249` -> `AKU-0049`, `AKU-0201`, `AKU-0034`, `AKU-0219`
- `AKU-0304` -> `AKU-0010`, `AKU-0163`, `AKU-0220`
- `AKU-0250` -> `AKU-0048`, `AKU-0080`, `AKU-0032`
- `AKU-0305` -> `AKU-0010`, `AKU-0087`, `AKU-0163`, `AKU-0220`
- `AKU-0251`, `AKU-0265` -> `AKU-0095`, `AKU-0217`, `AKU-0243`
- `AKU-0255`, `AKU-0282` -> `AKU-0160`, `AKU-0166`

### Keep as conceptual notes

- `AKU-0256`, `AKU-0292`-`AKU-0294` -> `AKU-0003` only as degree/fractal analogy.
- `AKU-0252`, `AKU-0295`-`AKU-0298` -> no rule merge; optional note near price/time analysis.

### Keep separate from first pool

- `intraday-l02-positive-lock`: all AKU.
- `intraday-l10-trading-technique`: stop/news/trade management AKU, unless later linked to a specific verified wave pattern.

## Review template

```yaml
candidate:
  pool2_aku: AKU-
  first_pool_aku:
    - AKU-
decision: accept_related | reject | keep_conceptual | needs_more_review
relation_field_to_edit_later: related_aku | extends_aku | contradicts_aku | none
reviewed_by: Anton
reviewed_at: YYYY-MM-DD
comment: ""
```
