"""Neely Rule Identifier (Гл.3 стр.3-22).

Given three consecutive monowaves m0, m1, m2:
- m2/m1 ratio → Rule 1-7 (classifyRule, AKU-0141)
- m0/m1 ratio → Condition a-f (classifyCond, AKU-0142)
- Rule → probable structural label (:5 / :F3 / ?) (AKU-0144)
"""
from __future__ import annotations
import math
from .monowaves import Pivot


FIB_TOL = 0.04  # ±4% Fibonacci tolerance (AKU "±4%", стр.3-34)


def classify_rule(m1: float, m2: float) -> int:
    """m2/m1 → Rule 1-7. Returns 0 if undefined."""
    if m1 == 0 or math.isnan(m1) or math.isnan(m2):
        return 0
    r = m2 / m1
    if abs(r - 0.618) <= 0.618 * FIB_TOL:
        return 3                   # right on 61.8% line
    if r < 0.382:
        return 1
    if r < 0.618:
        return 2
    if r < 1.000:
        return 4
    if r < 1.618:
        return 5
    if r <= 2.618:
        return 6
    return 7


def classify_cond(rule: int, m0: float, m1: float) -> str:
    """m0/m1 → Condition a-f based on rule."""
    if rule == 0 or m1 == 0 or math.isnan(m0) or math.isnan(m1):
        return ""
    r = m0 / m1
    if rule == 1:
        return "a" if r < 0.618 else "b" if r < 1.0 else "c" if r < 1.618 else "d"
    if rule == 2:
        return ("a" if r < 0.382 else "b" if r < 0.618 else "c" if r < 1.0
                else "d" if r <= 1.618 else "e")
    if rule == 3:
        return ("a" if r < 0.382 else "b" if r < 0.618 else "c" if r < 1.0
                else "d" if r < 1.618 else "e" if r <= 2.618 else "f")
    if rule == 4:
        return ("a" if r < 0.382 else "b" if r < 1.0 else "c" if r < 1.618
                else "d" if r <= 2.618 else "e")
    # rules 5-7
    return "a" if r < 1.0 else "b" if r < 1.618 else "c" if r <= 2.618 else "d"


# ── EPIC 0: Структурные списки Гл.3 (AKU-0148-0150, 0167-0170) ──────────────
# Семантика скобок (AKU-0147): без скобок=норма(1.0), (..)=ниже(0.6), [..]=ещё ниже(0.3)
_W_NORM, _W_PAREN, _W_BRACK = 1.0, 0.6, 0.3

# Каждый элемент: (label, weight). Порядок = убывание вероятности (как в книге).
_RULE_LISTS: dict[int, list[tuple[str, float]]] = {
    # AKU-0148: {:5, (:c3), (x:c3), [:sL3], [:s5]}
    1: [(":5", _W_NORM), (":c3", _W_PAREN), ("x:c3", _W_PAREN),
        (":sL3", _W_BRACK), (":s5", _W_BRACK)],
    # AKU-0149: {:5, (:sL3), [:c3], [:s5]}
    2: [(":5", _W_NORM), (":sL3", _W_PAREN), (":c3", _W_BRACK), (":s5", _W_BRACK)],
    # AKU-0150: {:F3, :c3, :s5, :5, (:sL3), [:L5]}  — граница импульс/коррекция
    3: [(":F3", _W_NORM), (":c3", _W_NORM), (":s5", _W_NORM), (":5", _W_NORM),
        (":sL3", _W_PAREN), (":L5", _W_BRACK)],
    # AKU-0168: {:F3, :c3, :5, :L5, (:L3)}
    5: [(":F3", _W_NORM), (":c3", _W_NORM), (":5", _W_NORM), (":L5", _W_NORM),
        (":L3", _W_PAREN)],
}

# AKU-0167: Правило 4 — списки зависят от Условия (a-e)
_RULE4_BY_COND: dict[str, list[tuple[str, float]]] = {
    "a": [(":F3", _W_NORM), (":c3", _W_NORM), (":s5", _W_NORM), (":sL3", _W_BRACK)],
    "b": [(":F3", _W_NORM), (":c3", _W_NORM), (":s5", _W_NORM),
          (":sL3", _W_PAREN), ("x:c3", _W_PAREN), (":L5", _W_BRACK)],
    "c": [(":c3", _W_NORM), (":F3", _W_PAREN), ("x:c3", _W_PAREN)],
    "d": [(":F3", _W_NORM), (":c3", _W_PAREN), ("x:c3", _W_PAREN)],
    "e": [(":F3", _W_NORM), ("x:c3", _W_PAREN), (":c3", _W_BRACK)],
}

# AKU-0169/0170: Правило 6-7 — возможна любая структура; favor по тексту.
# Дальнейшее уточнение — через последовательности Индикаторов Положения (стр.3-61).
_RULE_67_FAVOR: list[tuple[str, float]] = [
    (":5", _W_PAREN), (":s5", _W_PAREN), (":L5", _W_PAREN),
    (":L3", _W_PAREN), (":F3", _W_BRACK), (":c3", _W_BRACK),
]


def rule_to_structure_list(rule: int, cond: str = "") -> list[tuple[str, float]]:
    """Полный структурный список m1 по Правилу (+Условие для Пр.4).

    Возвращает упорядоченный список (label, weight) из Гл.3.
    Это замена наивному rule_to_structure: Правило 6-7 больше НЕ '?',
    а широкий список с favor-весами (AKU-0169/0170).
    """
    if rule == 4:
        return list(_RULE4_BY_COND.get(cond, _RULE4_BY_COND["a"]))
    if rule in _RULE_LISTS:
        return list(_RULE_LISTS[rule])
    if rule in (6, 7):
        return list(_RULE_67_FAVOR)
    return []


def rule_to_structure(rule: int, cond: str = "") -> str:
    """Наиболее вероятная метка m1 (вершина структурного списка).

    Backward-compatible: при rule 6-7 теперь возвращает favor-метку (:5),
    а не '?'. Старые вызовы без cond продолжают работать.
    """
    lst = rule_to_structure_list(rule, cond)
    return lst[0][0] if lst else ""


def structure_to_base(struct: str) -> int:
    """:5/:s5/:L5 → 5; :F3/:c3/:sL3/:L3/x:c3 → 3; ? → 0.

    Семантика: цифра 5 в метке → пятёрка (импульсный сегмент);
    цифра 3 → тройка (коррекционный сегмент). Префиксы (F/c/s/L/x)
    задают Индикатор Положения, но не меняют базу 3 vs 5.
    """
    if struct in ("", "?"):
        return 0
    if "5" in struct:
        return 5
    if "3" in struct:
        return 3
    return 0


def classify_pivots(pivots: list[Pivot]) -> None:
    """Mutate pivots in place: fill rule_no / cond_letter using m0, m1, m2 ladder.

    pivots[i].price_len is the length of monowave that ENDED at pivots[i].
    Classification applies to PREVIOUS monowave m1 = pivots[i-1].price_len:
    - m0 = pivots[i-2].price_len
    - m1 = pivots[i-1].price_len
    - m2 = pivots[i].price_len
    """
    for i in range(2, len(pivots)):
        m0 = pivots[i-2].price_len
        m1 = pivots[i-1].price_len
        m2 = pivots[i].price_len
        rule = classify_rule(m1, m2)
        cond = classify_cond(rule, m0, m1)
        # Attach to PREVIOUS pivot (m1 is the wave whose structure we classify)
        pivots[i-1].rule_no = rule
        pivots[i-1].cond_letter = cond
        # EPIC 0: полный структурный список (AKU-0148-0150, 0167-0170)
        slist = rule_to_structure_list(rule, cond)
        pivots[i-1].struct_list = slist
        pivots[i-1].struct_label = slist[0][0] if slist else ""
