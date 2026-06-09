# Pine vs Python — Parity Audit

**Дата:** 2026-06-09  
**Коммит Pine:** `5fc51f2` (после спринтов FIX-1..4)  
**Методология:** синтетические кейсы → Python `confirm_*` / `match_figures` vs задокументированное поведение Pine

---

## Сводка расхождений

| ID | Паттерн | Кейс | Python | Pine | Тип |
|----|---------|------|--------|------|-----|
| D1 | Flat | C < 61.8%A (failed-c) | ✅ confirmed (C — нейтральный) | ❌ rejected (C — обязательный) | Pine строже |
| D2 | Double Corr | Y < 61.8%W | ✅ confirmed (Y не проверяется) | ❌ rejected | Pine строже |
| D3 | Zigzag | любой зигзаг | ✅ matched | ❌ suppressed | ожидаемо, блокер OCR |
| D4 | Triangle | e ≥ c при n≥6 | ✅ ok (e не проверяется) | ❌ rejected | Pine строже |
| D5 | Impulse | W2 > 61.8%W1 | ✅ confirmed (W=warning) | ❌ rejected (r4=mandatory) | Pine строже |

**Pine строже Python** во всех случаях кроме D3. Это означает меньше ложных сигналов в Pine.

---

## D1 — Flat: порог C-волны

**Причина:** Python `confirm_flat` использует `C ≈ A (80–120%)` с severity=`N` (нейтральный, не блокирует).  
Pine `hybridFlatOK` / `confirmFlat` требует `C ≥ 61.8%A` как обязательное условие.

| Кейс | B/A | C/A | Python | Pine |
|------|-----|-----|--------|------|
| F1 нормальная | 1.00 | 1.00 | ok | ok |
| **F2 failed-c** | **1.00** | **0.50** | **ok** | **rej** |
| F3 extended | 1.00 | 1.50 | ok | ok |
| F4 слабый B | 0.50 | 1.00 | rej | rej |

**Вывод:** Flat с C < 61.8%A ("неудавшаяся-с" в слабом виде) Python принимает, Pine отклоняет.  
Это намеренное решение: Pine реализует минимальный порог Нили. Python нужно выровнять — добавить `C < 61.8%A → severity E`.

**Действие:** обновить `confirm.py::confirm_flat` — изменить `C ≈ A` с neutral на error при `C < 0.618`.

---

## D2 — Double Correction: Y-волна

**Причина:** Python `_try_double_corr` проверяет только X/W ratio (0.1–0.618). Y-волна не проверяется вообще.  
Pine `hybridDoubleCorrOK` требует `Y ≥ 61.8%W`.

| Кейс | X/W | Y/W | Python | Pine |
|------|-----|-----|--------|------|
| DC1 нормальный | 0.40 | 1.20 | ok | ok |
| **DC2 малая Y** | **0.40** | **0.30** | **ok** | **rej** |
| DC3 большой X | 0.70 | 1.40 | rej | rej |

**Действие:** добавить Y-check в `python/ewb/figures.py::_try_double_corr`:
```python
len_y = abs(prices[3] - prices[2])
y_ratio = len_y / len1
if not (y_ratio >= 0.618):
    return None
```

---

## D3 — Zigzag: подавлен в Pine (ожидаемо)

**Причина:** намеренно — Zigzag неотличим от хвоста Импульса без Индикаторов Положения (Гл.3).  
**Блокер:** OCR Глав 2-4.

| Кейс | B/A | C/A | Python | Pine |
|------|-----|-----|--------|------|
| ZZ1 чистый | 0.30 | 1.00 | matched | suppressed |
| ZZ2 граница | 0.59 | 0.90 | matched | suppressed |

**Действие:** нет — до OCR Гл.3 и реализации Индикаторов Положения.

---

## D4 — Triangle: проверка e < c

**Причина:** Python `confirm_triangle` проверяет только `c < a` и `d < b`. Pine добавляет `e < c` при n≥6.

| Кейс | a | b | c | d | e | Python | Pine |
|------|---|---|---|---|---|--------|------|
| T1 идеальный | 20 | 15 | 12 | 9 | 6 | ok | ok |
| **T2 e=14 > c=12** | **20** | **15** | **12** | **9** | **14** | **ok** | **rej** |
| T3 d>b нарушение | 20 | 15 | 12 | 16 | 11 | rej | rej |

**Действие:** добавить e<c в `python/ewb/confirm.py::confirm_triangle`:
```python
if len(prices) >= 6:
    w5 = abs(prices[5] - prices[4])
    ok_e = w5 < w3
    results.append(CheckResult(ok_e, "O" if ok_e else "W",
        "e<c" if ok_e else f"e≥c e/c={w5/w3:.2f}", "AKU-0018"))
```

---

## D5 — Impulse: глубина W2

**Причина:** Python `imp_w2_retrace` имеет severity=`W` (warning, не блокирует `all_passed`).  
Pine: r4 (`W2/W1 ≤ 0.618`) включён в `bool ok` → обязательное.

| Кейс | W2/W1 | overlap | Python | Pine |
|------|-------|---------|--------|------|
| I1 нормальный | 0.50 | нет | ok | ok |
| **I2 глубокий W2** | **0.80** | **нет** | **ok (⚠️ warn)** | **rej** |
| I3 W2/W4 overlap | 0.40 | да | rej | rej |
| I4 W4 пробивает | 0.50 | да | rej | rej |

**Примечание:** Неоднозначно. Нили допускает глубокий W2 в некоторых случаях (до 100%). AKU-0127 — правило "нормального" Импульса, не абсолютное. Текущий подход Pine (обязательный) даёт меньше ложных срабатываний.

**Действие (опционально):** понизить r4 в Pine до warning (`bool ok` без r4, оставить в msg как ⚠) — или повысить Python до Error. Требует анализа backtest impact. **Не трогать без данных.**

---

## Итог: статус исправлений

| Приоритет | Файл | Изменение | Статус |
|-----------|------|-----------|--------|
| 🔴 Высокий | `python/ewb/figures.py::_try_double_corr` | Добавить Y ≥ 61.8%W check | ✅ done `8556c14` |
| 🟡 Средний | `python/ewb/confirm.py::confirm_flat` | C ≥ 61.8%A → severity E (не N) | ✅ done `577ad9d` |
| 🟡 Средний | `python/ewb/confirm.py::confirm_triangle` | Добавить e < c check при len≥6 | ✅ done `577ad9d` |
| ⚪ Обсудить | `pine/ewb_monowaves_mtf.pine` r4 | W2 retrace mandatory → **нет backtest impact** (0 impulse trades), оставить как есть | ✅ закрыт |
| ⚪ Заблокировано | Zigzag | Ждём OCR Гл.3 | 🔒 blocked |
| 🟢 Новое | `matchFigure` hybrid fallback | Импульс через Rule 6-7: добавлен гибридный fallback (direct geometry) | ✅ done |

## Примечание о Triangle severity (D4)

Python `confirm_triangle` (и e<c проверка) использует severity=`W` (warning), что означает `all_passed=True` даже при нарушении.
Pine использует жёсткий `bool ok = r45 and r5e`. Это осознанное расхождение:
- Изменение на severity=`E` сломало бы `_try_triangle` (triangles больше не находились бы)
- **Backtest impact = 0** (стратегия торгует только flat/DC, не triangle) → оставляем как есть

## D5 — W2 retrace

**Закрыт без изменений**: 0 impulse trades в backtest parquet. Pine mandatory строже → меньше false positives.

*Аудит завершён 2026-06-09. Обновлён 2026-06-09.*

