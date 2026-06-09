"""Figure matcher (Sprint 0.5 — hybrid geometry+rules).

Old approach (Pine 1:1): map each monowave to base structure 5/3/0 via
rule_to_structure(rule_no), then look for [5,3,5,3,5] etc. PROBLEM: in real
impulses W2/W4 typically yield Rule 6-7 (W_next/W_this > 1.618), which maps
to "?" not ":3", so impulse seq becomes [5,?,5,?,5] and never matches.

New approach: directly scan windows of N pivots, validate by:
  1. monowave directions alternate correctly for figure type
  2. confirmation rules from confirm.py pass (no Error severity)
  3. rule_no still attached to each pivot for later analysis / ML features

Greedy non-overlapping selection with priority: impulse > triangle > flat
> double_corr > zigzag. Within same start, prefer "confirmed".
"""
from __future__ import annotations
from dataclasses import dataclass, field
from .monowaves import Pivot
from .rules import rule_to_structure, structure_to_base
from .confirm import (
    confirm_impulse, confirm_zigzag, confirm_flat, confirm_triangle,
    all_passed, CheckResult,
)


@dataclass
class Figure:
    type: str
    direction: str
    start_idx: int
    end_idx: int                                       # bar of LAST pivot (extremum)
    confirmed_idx: int = -1                            # bar when figure became visible (set externally)
    pivots: list[Pivot] = field(default_factory=list)
    confirmed: bool = True
    checks: list[CheckResult] = field(default_factory=list)
    motion_labels: list[str] = field(default_factory=list)
    structure_labels: list[str] = field(default_factory=list)

    @property
    def start_price(self) -> float: return self.pivots[0].price
    @property
    def end_price(self) -> float: return self.pivots[-1].price
    @property
    def amplitude(self) -> float: return abs(self.end_price - self.start_price)
    @property
    def duration(self) -> int: return self.end_idx - self.start_idx

    def to_dict(self) -> dict:
        return {
            "type": self.type, "direction": self.direction,
            "start_idx": self.start_idx, "end_idx": self.end_idx,
            "duration": self.duration, "amplitude": self.amplitude,
            "confirmed": self.confirmed, "n_checks": len(self.checks),
            "n_errors": sum(1 for c in self.checks if c.severity == "E" and not c.ok),
            "n_warnings": sum(1 for c in self.checks if c.severity == "W" and not c.ok),
            "pivot_prices": [p.price for p in self.pivots],
            "pivot_indices": [p.idx for p in self.pivots],
        }


def _directions_alternate(pivots: list[Pivot], start: int, count: int) -> bool:
    """Check that monowave directions alternate over [start, start+count).

    pivots[i].direction = direction of monowave that ENDED at pivots[i].
    For a clean figure, consecutive monowaves must alternate +1, -1, +1, ...
    """
    for k in range(start + 1, start + count):
        if pivots[k].direction == pivots[k - 1].direction:
            return False
    return True


def _try_impulse(pivots: list[Pivot], i: int) -> Figure | None:
    """Try to match impulse at pivots[i..i+5] (6 pivots = 5 waves)."""
    if i + 5 >= len(pivots):
        return None
    pts = pivots[i:i + 6]

    # Monowaves 1..5 end at pts[1..5]. They must alternate in direction.
    if not _directions_alternate(pts, 1, 5):
        return None

    # W1 direction (= overall impulse direction) from pts[1].direction
    first_dir = pts[1].direction
    direction = "up" if first_dir > 0 else "down"

    prices = [p.price for p in pts]
    checks = confirm_impulse(prices, direction)
    confirmed = all_passed(checks)

    return Figure(
        type="impulse", direction=direction,
        start_idx=pts[0].idx, end_idx=pts[-1].idx,
        pivots=pts, confirmed=confirmed, checks=checks,
        motion_labels=["0", "1", "2", "3", "4", "5"],
        structure_labels=[":5", ":F3", ":5", ":F3", ":L5"],
    )


def _try_triangle(pivots: list[Pivot], i: int) -> Figure | None:
    """Triangle: 6 pivots, alternating, contracting (W3<W1, W4<W2)."""
    if i + 5 >= len(pivots):
        return None
    pts = pivots[i:i + 6]
    if not _directions_alternate(pts, 1, 5):
        return None

    first_dir = pts[1].direction
    direction = "up" if first_dir > 0 else "down"
    prices = [p.price for p in pts]
    checks = confirm_triangle(prices)
    confirmed = all_passed(checks)

    # A triangle should NOT pass impulse test (we don't want to double-count)
    imp_checks = confirm_impulse(prices, direction)
    if all_passed(imp_checks):
        # geometry says it's also a valid impulse → not a triangle
        return None

    return Figure(
        type="triangle", direction=direction,
        start_idx=pts[0].idx, end_idx=pts[-1].idx,
        pivots=pts, confirmed=confirmed, checks=checks,
        motion_labels=["0", "a", "b", "c", "d", "e"],
        structure_labels=[":F3", ":c3", ":c3", ":sL3", ":L3"],
    )


def _try_flat(pivots: list[Pivot], i: int) -> Figure | None:
    """Flat: 4 pivots = 3 waves (A-B-C). B retraces ≥61.8% A, C ≈ A."""
    if i + 3 >= len(pivots):
        return None
    pts = pivots[i:i + 4]
    if not _directions_alternate(pts, 1, 3):
        return None

    first_dir = pts[1].direction
    direction = "up" if first_dir > 0 else "down"
    prices = [p.price for p in pts]
    checks = confirm_flat(prices)
    confirmed = all_passed(checks)

    return Figure(
        type="flat", direction=direction,
        start_idx=pts[0].idx, end_idx=pts[-1].idx,
        pivots=pts, confirmed=confirmed, checks=checks,
        motion_labels=["0", "A", "B", "C"],
        structure_labels=[":F3", ":c3", ":?5"],
    )


def _try_zigzag(pivots: list[Pivot], i: int) -> Figure | None:
    """Zigzag: 4 pivots, alternating. B < A (deep retracement, B<=A by AKU-0014)
    AND B retraces LESS than 61.8% of A (else it's a flat)."""
    if i + 3 >= len(pivots):
        return None
    pts = pivots[i:i + 4]
    if not _directions_alternate(pts, 1, 3):
        return None

    first_dir = pts[1].direction
    direction = "up" if first_dir > 0 else "down"
    prices = [p.price for p in pts]
    a = abs(prices[1] - prices[0])
    b = abs(prices[2] - prices[1])
    if a <= 0:
        return None
    # Discriminator: B must be SHALLOWER than flat threshold
    if b / a >= 0.618:
        return None  # this looks like a flat, not a zigzag

    checks = confirm_zigzag(prices)
    confirmed = all_passed(checks)

    return Figure(
        type="zigzag", direction=direction,
        start_idx=pts[0].idx, end_idx=pts[-1].idx,
        pivots=pts, confirmed=confirmed, checks=checks,
        motion_labels=["0", "A", "B", "C"],
        structure_labels=[":5", ":F3", ":L5"],
    )


def _try_double_corr(pivots: list[Pivot], i: int) -> Figure | None:
    """Double Correction: 4 pivots, middle wave (X) < 61.8% of first.
    Note: at this point flat/zigzag would have matched if applicable.
    This is the fallback for small-middle 3-wave structures."""
    if i + 3 >= len(pivots):
        return None
    pts = pivots[i:i + 4]
    if not _directions_alternate(pts, 1, 3):
        return None

    prices = [p.price for p in pts]
    direction = "up" if pts[1].direction > 0 else "down"
    len1 = abs(prices[1] - prices[0])
    lenX = abs(prices[2] - prices[1])
    lenY = abs(prices[3] - prices[2])
    if len1 <= 0:
        return None
    x_ratio = lenX / len1
    y_ratio = lenY / len1
    # x must be small but not vanishing; Y must be significant (≥61.8% W)
    if not (0.1 < x_ratio < 0.618):
        return None
    if y_ratio < 0.618:
        return None
    return Figure(
        type="double_corr", direction=direction,
        start_idx=pts[0].idx, end_idx=pts[-1].idx, pivots=pts,
        confirmed=True,
        checks=[CheckResult(True, "O", f"x={x_ratio*100:.0f}%<61.8% y={y_ratio*100:.0f}%≥61.8%", "AKU-0185")],
        motion_labels=["0", "W", "X", "Y"],
        structure_labels=[":F3", "x:c3", ":F3"],
    )


# Priority for greedy selection. Higher score wins.
def _figure_score(f: Figure) -> tuple:
    type_rank = {"impulse": 5, "triangle": 4, "flat": 3,
                 "double_corr": 2, "zigzag": 1}
    return (int(f.confirmed), type_rank.get(f.type, 0), -f.start_idx)


def match_figures(pivots: list[Pivot]) -> list[Figure]:
    """Sliding-window match with priority + non-overlap.

    For each pivot index i, try all figure types. Collect candidates, then
    greedily pick by score, advancing past consumed pivots.
    """
    n = len(pivots)
    if n < 4:
        return []

    # Phase 1: collect all candidates
    candidates: list[Figure] = []
    for i in range(n):
        for fn in (_try_impulse, _try_triangle, _try_flat,
                   _try_zigzag, _try_double_corr):
            fig = fn(pivots, i)
            if fig is not None:
                candidates.append((i, fig))

    # Phase 2: greedy non-overlap (operating on pivot indices, not bar indices)
    # Sort candidates by (score desc, start asc) and pick non-overlapping ones.
    indexed = []
    for i, fig in candidates:
        # find pivot index range
        size = 6 if fig.type in ("impulse", "triangle") else 4
        indexed.append((i, i + size - 1, fig))
    # Sort by score desc, then by start asc
    indexed.sort(key=lambda t: (-_figure_score(t[2])[0],
                                 -_figure_score(t[2])[1], t[0]))

    used = [False] * n
    selected: list[Figure] = []
    for (s, e, fig) in indexed:
        if e >= n:
            continue
        if any(used[k] for k in range(s, e + 1)):
            continue
        # Mark INTERIOR as used; allow next figure to share boundary pivot
        for k in range(s + 1, e):
            used[k] = True
        selected.append(fig)

    # Sort final list by start pivot for readability
    selected.sort(key=lambda f: f.start_idx)
    return selected
