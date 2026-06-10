"""EPIC 6 — Post-pattern projection / Energy Rating (Neely Гл.5-7).

After a pattern COMPLETES, Neely's rules constrain the next move. This is the
forward-looking layer: "where does price go after this structure".

Grounded rules:
- Impulse (5 waves): the following correction moves OPPOSITE the impulse and
  retraces toward the Wave-4 territory; deeper toward Wave-2. It must not
  exceed the impulse end (else the count was wrong / impulse continues).
- Zigzag: after an (extended) zigzag the market reverses and retraces >61.8%
  of wave-c before c-end is exceeded (AKU-0023).
- Contracting triangle: a thrust in the breakout direction must exceed the
  triangle extreme; thrust magnitude ~ widest leg of the triangle (AKU-0038/39).
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class NextMove:
    direction: str          # "up" / "down" — expected next move
    target_lo: float        # near edge of expected zone
    target_hi: float        # far edge of expected zone
    invalidation: float     # level that voids this projection
    note: str
    confidence: str         # "low" / "medium" / "high"

    def to_dict(self) -> dict:
        return {
            "next_direction": self.direction,
            "target_lo": round(self.target_lo, 4),
            "target_hi": round(self.target_hi, 4),
            "invalidation": round(self.invalidation, 4),
            "note": self.note,
            "confidence": self.confidence,
        }


def project_next_move(figure) -> NextMove | None:
    """Project the move that should follow a CONFIRMED pattern."""
    if not getattr(figure, "confirmed", False):
        return None
    pts = getattr(figure, "pivots", None)
    if not pts:
        return None
    prices = [p.price for p in pts]
    up = figure.direction == "up"

    if figure.type == "impulse" and len(prices) >= 6:
        # p0..p5. Correction is opposite; retrace toward W4 (p4) then W2 (p2).
        w4 = prices[4]
        w2 = prices[2]
        end = prices[5]
        return NextMove(
            direction="down" if up else "up",
            target_lo=min(w4, w2), target_hi=max(w4, w2),
            invalidation=end,                 # exceeding W5 end voids the top
            note="Пост-импульс: коррекция к зоне W4, глубже к W2; не выше конца W5.",
            confidence="medium",
        )

    if figure.type == "zigzag" and len(prices) >= 4:
        # AKU-0023: reversal retraces >61.8% of wave-c.
        c_start = prices[2]
        c_end = prices[3]
        c_len = abs(c_end - c_start)
        retr = 0.618 * c_len
        tgt = c_end - retr if up else c_end + retr   # opposite to C direction
        return NextMove(
            direction="down" if up else "up",
            target_lo=min(c_end, tgt), target_hi=max(c_end, tgt),
            invalidation=c_end,                # breaking C-end first voids it
            note="Пост-зигзаг (AKU-0023): разворот, откат >61.8% волны-c.",
            confidence="medium",
        )

    if figure.type == "triangle" and len(prices) >= 6:
        # AKU-0038/39: thrust exceeds triangle extreme; magnitude ~ widest leg.
        widest = abs(prices[1] - prices[0])     # wave-a, widest in contracting
        # breakout from e-end (p5) in the pre-triangle trend direction
        e_end = prices[5]
        tgt = e_end + widest if up else e_end - widest
        return NextMove(
            direction="up" if up else "down",
            target_lo=min(e_end, tgt), target_hi=max(e_end, tgt),
            invalidation=prices[0],            # back into triangle voids thrust
            note="Пост-треугольник (AKU-0038/39): thrust ~ ширина волны-a, пробой экстремума.",
            confidence="medium",
        )

    return None
