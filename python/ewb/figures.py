"""Figure matcher — Neely Structural Series A-E (Гл.4).

Iterates over confirmed monowave pivots, maintains a sliding window of base
structures (5/3) inferred from rule_no, and recognises:
- Impulse  (5-3-5-3-5)
- Flat     (3-3-5)
- Triangle (3-3-3-3-3)
- Double Correction (3-3-3 with small x-wave)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from .monowaves import Pivot
from .rules import rule_to_structure, structure_to_base
from .confirm import (
    confirm_impulse, confirm_flat, confirm_triangle,
    all_passed, summary, CheckResult,
)


@dataclass
class Figure:
    type: str                              # "impulse" | "flat" | "triangle" | "double_corr"
    direction: str                         # "up" | "down"
    start_idx: int                         # bar index of starting pivot
    end_idx: int                           # bar index of ending pivot
    pivots: list[Pivot] = field(default_factory=list)
    confirmed: bool = True                 # passed Error-severity checks
    checks: list[CheckResult] = field(default_factory=list)
    motion_labels: list[str] = field(default_factory=list)  # e.g. ["0","1","2","3","4","5"]
    structure_labels: list[str] = field(default_factory=list)  # e.g. [":5",":F3",":5",...]

    @property
    def start_price(self) -> float:
        return self.pivots[0].price

    @property
    def end_price(self) -> float:
        return self.pivots[-1].price

    @property
    def amplitude(self) -> float:
        return abs(self.end_price - self.start_price)

    @property
    def duration(self) -> int:
        return self.end_idx - self.start_idx

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "direction": self.direction,
            "start_idx": self.start_idx,
            "end_idx": self.end_idx,
            "duration": self.duration,
            "amplitude": self.amplitude,
            "confirmed": self.confirmed,
            "n_checks": len(self.checks),
            "n_errors": sum(1 for c in self.checks if c.severity == "E" and not c.ok),
            "n_warnings": sum(1 for c in self.checks if c.severity == "W" and not c.ok),
            "pivot_prices": [p.price for p in self.pivots],
            "pivot_indices": [p.idx for p in self.pivots],
        }


def _figure_direction(p0: float, p1: float) -> str:
    return "up" if p1 > p0 else "down"


def _build_base_seq(pivots: list[Pivot]) -> list[int]:
    """Map each pivot's previous monowave to base structure 5/3/0 via rule_no.

    seq[i] = base structure of monowave that ENDED at pivots[i]
    (using rule_no on previous pivot which classifies that monowave).
    """
    seq = []
    for p in pivots:
        st = rule_to_structure(p.rule_no) if p.rule_no else ""
        seq.append(structure_to_base(st))
    return seq


def match_figures(pivots: list[Pivot]) -> list[Figure]:
    """Scan pivots, recognise figures by Structural Series.

    Strategy: non-overlapping greedy. Once a figure is confirmed at position i,
    skip to the end of that figure.
    """
    if len(pivots) < 4:
        return []

    seq = _build_base_seq(pivots)
    figures: list[Figure] = []
    n = len(pivots)
    i = 0

    while i < n:
        # 5-3-5-3-5 Impulse — need 6 pivots (p0..p5)
        if i + 5 < n and _is_impulse_seq(seq, i + 1):
            fig = _try_impulse(pivots, i)
            if fig:
                figures.append(fig)
                i = i + 5   # next figure can share last pivot
                continue

        # 3-3-3-3-3 Triangle — 6 pivots
        if i + 5 < n and _is_triangle_seq(seq, i + 1):
            fig = _try_triangle(pivots, i)
            if fig:
                figures.append(fig)
                i = i + 5
                continue

        # 3-3-5 Flat — 4 pivots
        if i + 3 < n and _is_flat_seq(seq, i + 1):
            fig = _try_flat(pivots, i)
            if fig:
                figures.append(fig)
                i = i + 3
                continue

        # 3-3-3 Double correction — 4 pivots
        if i + 3 < n and _is_three_threes(seq, i + 1):
            fig = _try_double_corr(pivots, i)
            if fig:
                figures.append(fig)
                i = i + 3
                continue

        i += 1

    return figures


def _is_impulse_seq(seq: list[int], start: int) -> bool:
    if start + 5 > len(seq):
        return False
    return seq[start:start+5] == [5, 3, 5, 3, 5]


def _is_triangle_seq(seq: list[int], start: int) -> bool:
    if start + 5 > len(seq):
        return False
    return seq[start:start+5] == [3, 3, 3, 3, 3]


def _is_flat_seq(seq: list[int], start: int) -> bool:
    if start + 3 > len(seq):
        return False
    return seq[start:start+3] == [3, 3, 5]


def _is_three_threes(seq: list[int], start: int) -> bool:
    if start + 3 > len(seq):
        return False
    return seq[start:start+3] == [3, 3, 3]


def _try_impulse(pivots: list[Pivot], i: int) -> Figure | None:
    pts = pivots[i:i+6]
    prices = [p.price for p in pts]
    direction = _figure_direction(prices[0], prices[1])
    checks = confirm_impulse(prices, direction)
    confirmed = all_passed(checks)
    return Figure(
        type="impulse",
        direction=direction,
        start_idx=pts[0].idx,
        end_idx=pts[-1].idx,
        pivots=pts,
        confirmed=confirmed,
        checks=checks,
        motion_labels=["0","1","2","3","4","5"],
        structure_labels=[":5",":F3",":5",":F3",":L5"],
    )


def _try_triangle(pivots: list[Pivot], i: int) -> Figure | None:
    pts = pivots[i:i+6]
    prices = [p.price for p in pts]
    direction = _figure_direction(prices[0], prices[1])
    checks = confirm_triangle(prices)
    confirmed = all_passed(checks)
    return Figure(
        type="triangle",
        direction=direction,
        start_idx=pts[0].idx,
        end_idx=pts[-1].idx,
        pivots=pts,
        confirmed=confirmed,
        checks=checks,
        motion_labels=["0","a","b","c","d","e"],
        structure_labels=[":F3",":c3",":c3",":sL3",":L3"],
    )


def _try_flat(pivots: list[Pivot], i: int) -> Figure | None:
    pts = pivots[i:i+4]
    prices = [p.price for p in pts]
    direction = _figure_direction(prices[0], prices[1])
    checks = confirm_flat(prices)
    confirmed = all_passed(checks)
    return Figure(
        type="flat",
        direction=direction,
        start_idx=pts[0].idx,
        end_idx=pts[-1].idx,
        pivots=pts,
        confirmed=confirmed,
        checks=checks,
        motion_labels=["0","A","B","C"],
        structure_labels=[":F3",":c3",":?5"],
    )


def _try_double_corr(pivots: list[Pivot], i: int) -> Figure | None:
    """3-3-3 with small middle (x-wave) — Double Correction (AKU-0185/0191)."""
    pts = pivots[i:i+4]
    prices = [p.price for p in pts]
    direction = _figure_direction(prices[0], prices[1])
    len1 = abs(prices[1] - prices[0])
    lenX = abs(prices[2] - prices[1])
    if len1 <= 0:
        return None
    x_ratio = lenX / len1
    if x_ratio >= 0.618:    # x-wave too big → not a clear double correction
        return None
    return Figure(
        type="double_corr",
        direction=direction,
        start_idx=pts[0].idx,
        end_idx=pts[-1].idx,
        pivots=pts,
        confirmed=True,
        checks=[CheckResult(True, "O", f"x={x_ratio*100:.0f}%<61.8%", "AKU-0185")],
        motion_labels=["0","W","X","Y"],
        structure_labels=[":F3","x:c3",":F3"],
    )
