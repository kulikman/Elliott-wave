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


def rule_to_structure(rule: int) -> str:
    """Probable base structure for m1 by rule (first candidate from Structural List)."""
    if rule in (1, 2):
        return ":5"          # likely impulse component
    if rule in (3, 4, 5):
        return ":F3"         # likely corrective component
    if rule >= 6:
        return "?"           # needs position indicators (Гл.3 стр.3-60)
    return ""


def structure_to_base(struct: str) -> int:
    """:5 → 5, :F3/:c3/... → 3, ? → 0."""
    if struct.startswith(":5") or struct == ":5":
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
