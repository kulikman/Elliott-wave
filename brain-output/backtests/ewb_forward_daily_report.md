# EWB Forward Daily Report

Decision: **OBSERVE**

Меньше 30 закрытых forward-сделок. Реальные деньги и автоматизацию не включать.

## Metrics

| Scope | Trades | Win | Exp | PF | DD |
|---|---|---|---|---|---|
| Historical baseline | 1518 | 59.9% | 1.44% | 1.83 | -96.2% |
| Forward closed | 1 | 100.0% | 26.54% | n/a | 0.0% |

## Open Trades

| ID | Ticker | TF | Side | Pattern | Entry | SL | TP | P | Time |
|---|---|---|---|---|---|---|---|---|---|
| efd61e4bd3124279 | ISRG | 1d | long | flat | 426.6 | 328.9 | 524.4 | 66.7% | 2026-06-09 00:00:00+00:00 |
| fced5528679c4e27 | META | 1d | short | flat | 593 | 642.8 | 543.2 | 69.6% | 2026-06-05 00:00:00+00:00 |
| 8c227a7876f1ece9 | AVGO | 1d | short | double_corr | 418.9 | 624 | 213.9 | 100.0% | 2026-06-04 00:00:00+00:00 |
| 1ac464538f85c0e0 | LLY | 1d | short | flat | 1064 | 1338 | 790.7 | 69.6% | 2026-06-02 00:00:00+00:00 |

## Recently Closed

| Ticker | TF | Side | Pattern | Entry | Exit | Ret | Reason | Exit time |
|---|---|---|---|---|---|---|---|---|
| ARM | 1d | long | flat | 256.7 | 324.9 | 26.5% | tp | 2026-06-09 21:59:26.361375+00:00 |

## Operating Rule

- Пока decision = OBSERVE или PAPER ONLY, сделки используются только для статистики.
- Если появляется BLOCK, остановить новые входы и проверить repaint, цену исполнения, HTF context и SL/TP.
- Масштабировать риск можно только после стабильного forward-подтверждения, а не по historical baseline.
