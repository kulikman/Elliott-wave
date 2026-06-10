"""EPIC 3 — Wave-3 entry engine (Neely Гл.5, extension waves).

The strongest, most reliable Neely trade is the entry at the START of a third
wave: W1 completes as an impulsive :5, W2 retraces 38.2-61.8% (a healthy
pullback that does NOT break W1 start), and price then breaks W1 end in the
W1 direction — Wave 3 is underway.

This is a TREND-FOLLOWING setup (buy strength), the opposite of the existing
fade layer. It is gated behind a feature flag so the validated fade baseline
is untouched until W3 forward-metrics are proven on 30+ closed trades.

Setup geometry (long example, W1 up):
    p0 = W1 start, p1 = W1 end, p2 = W2 end (= W3 start)
    entry  = break of p1 (W1 end)
    stop   = p2 (W2 end)
    invalid= p0 (W1 start)  — if hit, the impulse count is wrong
    TP1/2/3 = entry + {1.0, 1.618, 2.618} * |W1|   (Гл.5 extension ratios)
"""
from __future__ import annotations
from dataclasses import dataclass, field

from .monowaves import Pivot
from .rules import structure_to_base


# Neely-healthy W2 retracement window for a tradeable Wave-3 setup.
W2_MIN_RETRACE = 0.382
W2_MAX_RETRACE = 0.618          # >61.8% → W1 relabels to :3 (EPIC 2), not a real impulse
# Extension targets measured from entry in W1 direction (Гл.5).
TP_MULTS = (1.0, 1.618, 2.618)


@dataclass
class Wave3Setup:
    direction: str              # "up" (long) / "down" (short)
    side: str                   # "long" / "short"
    w1_start: float
    w1_end: float
    w2_end: float
    w1_len: float
    w2_retrace: float           # fraction of W1
    entry_px: float
    stop_px: float
    invalid_px: float
    tp1: float
    tp2: float
    tp3: float
    entry_idx: int
    triggered: bool             # price has broken W1 end (W3 underway)
    struct_ok: bool             # W1 monowave compatible with :5
    rr1: float = 0.0            # reward(TP1):risk
    checks: list = field(default_factory=list)

    def to_signal(self, ticker: str, interval: str, ts: str) -> dict:
        """Render into the runtime signal contract (compatible with scanner)."""
        return {
            "pattern": "wave3",
            "interval": interval,
            "direction": self.direction,
            "side": self.side,
            "ticker": ticker,
            "recommended_action": "buy" if self.side == "long" else "sell",
            "entry_ts": ts,
            "entry_idx": int(self.entry_idx),
            "confirmed": bool(self.triggered and self.struct_ok),
            "risk_box": {
                "entry_px": self.entry_px,
                "stop_px": self.stop_px,
                "target_px": self.tp2,        # primary target = 1.618xW1
                "invalid_px": self.invalid_px,
                "tp1": self.tp1, "tp2": self.tp2, "tp3": self.tp3,
                "amplitude": self.w1_len,
            },
            "w2_retrace": round(self.w2_retrace, 3),
            "rr1": round(self.rr1, 2),
            "entry_zone": "wave3_breakout_of_W1_end",
            "stop": "below_W2_end",
            "target": "extension_1.0_1.618_2.618_of_W1",
            "source": "wave3_engine",
        }


def _struct_compatible_impulse(piv: Pivot) -> bool:
    """W1 monowave must be compatible with an impulsive :5 (EPIC 0 struct_list)."""
    if not piv.struct_list:
        return True   # unclassified edge pivot — don't block on missing data
    return any(structure_to_base(lbl) == 5 for lbl, _ in piv.struct_list)


def detect_wave3_setups(
    pivots: list[Pivot],
    last_price: float,
    last_idx: int,
) -> list[Wave3Setup]:
    """Scan pivot ladder for live Wave-3 setups.

    Uses the most recent completed W1(p0->p1) + W2(p1->p2) triples. A setup is
    `triggered` when last_price has broken beyond W1 end in the W1 direction.
    """
    setups: list[Wave3Setup] = []
    n = len(pivots)
    if n < 3:
        return setups

    # Walk triples ending at each pivot; the freshest (last) is most actionable.
    for i in range(n - 2):
        p0, p1, p2 = pivots[i], pivots[i + 1], pivots[i + 2]
        direction = "up" if p1.price > p0.price else "down"
        up = direction == "up"

        w1_len = abs(p1.price - p0.price)
        if w1_len <= 0:
            continue
        w2_len = abs(p2.price - p1.price)
        w2_retrace = w2_len / w1_len

        # W2 must be a healthy pullback (38.2-61.8%); deeper → EPIC 2 relabel.
        if not (W2_MIN_RETRACE <= w2_retrace <= W2_MAX_RETRACE):
            continue
        # W2 must NOT break W1 start (invalidation).
        if up and p2.price <= p0.price:
            continue
        if (not up) and p2.price >= p0.price:
            continue
        # W2 must retrace in the correct direction (pullback, not continuation).
        if up and p2.price >= p1.price:
            continue
        if (not up) and p2.price <= p1.price:
            continue

        struct_ok = _struct_compatible_impulse(p1)

        # Trigger: price breaks W1 end in W1 direction → W3 underway.
        triggered = last_price > p1.price if up else last_price < p1.price

        entry_px = p1.price
        stop_px = p2.price
        invalid_px = p0.price
        sgn = 1.0 if up else -1.0
        tp1 = entry_px + sgn * TP_MULTS[0] * w1_len
        tp2 = entry_px + sgn * TP_MULTS[1] * w1_len
        tp3 = entry_px + sgn * TP_MULTS[2] * w1_len

        risk = abs(entry_px - stop_px)
        rr1 = (abs(tp1 - entry_px) / risk) if risk > 0 else 0.0

        setups.append(Wave3Setup(
            direction=direction, side="long" if up else "short",
            w1_start=p0.price, w1_end=p1.price, w2_end=p2.price,
            w1_len=w1_len, w2_retrace=w2_retrace,
            entry_px=entry_px, stop_px=stop_px, invalid_px=invalid_px,
            tp1=tp1, tp2=tp2, tp3=tp3,
            entry_idx=last_idx, triggered=triggered, struct_ok=struct_ok,
            rr1=rr1,
        ))
    return setups
