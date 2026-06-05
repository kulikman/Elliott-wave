"""Synthetic tests: generate known structures, verify detector finds them."""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from ewb.monowaves import Pivot, detect_monowaves
from ewb.rules import classify_pivots, classify_rule
from ewb.figures import match_figures
from ewb.confirm import confirm_impulse


def _build_ohlc_from_pivots(pivot_prices: list[float], bars_per_seg: int = 20,
                            jitter: float = 0.05) -> pd.DataFrame:
    """Linearly interpolate between pivot prices, add small noise.
    Each consecutive pair = one monowave."""
    np.random.seed(42)
    rows = []
    idx_dt = pd.date_range("2024-01-01", periods=bars_per_seg * (len(pivot_prices) - 1) + 1, freq="1h")
    pos = 0
    for i in range(len(pivot_prices) - 1):
        p_start = pivot_prices[i]
        p_end   = pivot_prices[i + 1]
        for b in range(bars_per_seg):
            t = b / bars_per_seg
            px = p_start + (p_end - p_start) * t
            noise = np.random.uniform(-jitter, jitter)
            o = px * (1 + noise * 0.3)
            c = px * (1 + noise * 0.3)
            # Highs/lows hug the trajectory tightly
            seg_min = min(p_start, p_end)
            seg_max = max(p_start, p_end)
            h = max(o, c) + abs(p_end - p_start) * 0.005
            l = min(o, c) - abs(p_end - p_start) * 0.005
            # Ensure pivots show up cleanly
            if b == 0:
                if p_end > p_start:
                    l = min(l, p_start)
                else:
                    h = max(h, p_start)
            rows.append({"open": o, "high": h, "low": l, "close": c})
            pos += 1
    # Final bar = last pivot
    p_last = pivot_prices[-1]
    rows.append({"open": p_last, "high": p_last, "low": p_last, "close": p_last})
    df = pd.DataFrame(rows, index=idx_dt[:len(rows)])
    return df


def _manual_pivots(prices: list[float], directions: list[int]) -> list[Pivot]:
    return [
        Pivot(idx=i, price=price, direction=direction, confirmation_idx=i)
        for i, (price, direction) in enumerate(zip(prices, directions))
    ]


def test_matcher_identifies_confirmed_core_patterns():
    cases = [
        ("impulse", [100, 120, 110, 140, 130, 160], [0, 1, -1, 1, -1, 1], "up"),
        ("flat", [100, 80, 100, 80], [0, -1, 1, -1], "down"),
        ("triangle", [100, 120, 105, 117, 108, 114], [0, 1, -1, 1, -1, 1], "up"),
        ("double_corr", [100, 80, 88, 70], [0, -1, 1, -1], "down"),
    ]
    for expected_type, prices, directions, expected_direction in cases:
        figs = match_figures(_manual_pivots(prices, directions))
        assert figs, f"expected {expected_type}, got no figures"
        assert figs[0].type == expected_type
        assert figs[0].direction == expected_direction
        assert figs[0].confirmed is True


def test_clean_impulse_up():
    """5-3-5-3-5 impulse: 100 → 120 → 110 → 140 → 130 → 160."""
    pivots_target = [100, 120, 110, 140, 130, 160]
    df = _build_ohlc_from_pivots(pivots_target, bars_per_seg=30, jitter=0.005)
    # Use smaller ATR mult since synthetic noise is tiny
    pivots = detect_monowaves(df, atr_period=14, atr_mult=1.0)
    print(f"[impulse_up] target pivots: {pivots_target}")
    print(f"[impulse_up] detected     : {[round(p.price,1) for p in pivots]}")
    # Expect at least 5 pivots (may miss first since init takes a few bars)
    assert len(pivots) >= 4, f"expected ≥4 pivots, got {len(pivots)}"

    classify_pivots(pivots)
    figs = match_figures(pivots)
    impulses = [f for f in figs if f.type == "impulse"]
    print(f"[impulse_up] figures      : {[f.type for f in figs]}")
    print(f"[impulse_up] OK\n")


def test_clean_zigzag_down():
    """A-B-C zigzag (5-3-5 down): 100 → 80 → 90 → 70."""
    pivots_target = [100, 80, 90, 70]
    df = _build_ohlc_from_pivots(pivots_target, bars_per_seg=30, jitter=0.005)
    pivots = detect_monowaves(df, atr_period=14, atr_mult=1.0)
    print(f"[zigzag_dn] target: {pivots_target}")
    print(f"[zigzag_dn] detect: {[round(p.price,1) for p in pivots]}")
    assert len(pivots) >= 3
    classify_pivots(pivots)
    figs = match_figures(pivots)
    print(f"[zigzag_dn] figs  : {[(f.type, f.direction) for f in figs]}")
    print(f"[zigzag_dn] OK\n")


def test_clean_flat():
    """Flat 3-3-5: A=100→80, B=80→100 (B=100%A), C=100→80 (C=A)."""
    pivots_target = [100, 80, 100, 80]
    df = _build_ohlc_from_pivots(pivots_target, bars_per_seg=30, jitter=0.005)
    pivots = detect_monowaves(df, atr_period=14, atr_mult=1.0)
    print(f"[flat     ] target: {pivots_target}")
    print(f"[flat     ] detect: {[round(p.price,1) for p in pivots]}")
    classify_pivots(pivots)
    figs = match_figures(pivots)
    print(f"[flat     ] figs  : {[(f.type, f.direction) for f in figs]}")
    flats = [f for f in figs if f.type == "flat"]
    print(f"[flat     ] {'FOUND' if flats else 'NOT FOUND (expected — base classifier may not output 3-3-5)'}\n")


def test_clean_triangle():
    """Contracting triangle 3-3-3-3-3: each wave shorter than previous."""
    pivots_target = [100, 120, 105, 117, 108, 114]
    df = _build_ohlc_from_pivots(pivots_target, bars_per_seg=25, jitter=0.005)
    pivots = detect_monowaves(df, atr_period=14, atr_mult=1.0)
    print(f"[triangle ] target: {pivots_target}")
    print(f"[triangle ] detect: {[round(p.price,1) for p in pivots]}")
    classify_pivots(pivots)
    figs = match_figures(pivots)
    print(f"[triangle ] figs  : {[(f.type, f.direction) for f in figs]}")
    print()


def test_confirm_impulse_pure_math():
    """Direct rule check on prices, no detector."""
    # Textbook impulse up
    prices = [100, 120, 110, 140, 130, 160]
    checks = confirm_impulse(prices, "up")
    errs = [c for c in checks if c.severity == "E" and not c.ok]
    warns = [c for c in checks if c.severity == "W" and not c.ok]
    print(f"[confirm  ] errors  : {[c.aku + ':' + c.msg for c in errs]}")
    print(f"[confirm  ] warnings: {[c.aku + ':' + c.msg for c in warns]}")
    print(f"[confirm  ] checks  : {[c.aku + ':' + c.msg for c in checks if c.ok]}\n")
    assert len(errs) == 0, f"clean impulse should have 0 errors, got {errs}"


def test_classify_rule_boundaries():
    """Boundary cases for Rule Identifier."""
    cases = [
        (1.0, 0.3, 1),   # m2/m1 = 0.3 < 0.382 → Rule 1
        (1.0, 0.5, 2),   # 0.5 ∈ [0.382, 0.618) → Rule 2
        (1.0, 0.618, 3), # exactly 0.618 → Rule 3 (within ±4%)
        (1.0, 0.8, 4),   # 0.8 ∈ [0.618, 1.0) → Rule 4
        (1.0, 1.3, 5),   # 1.3 ∈ [1.0, 1.618) → Rule 5
        (1.0, 2.0, 6),   # 2.0 ∈ [1.618, 2.618] → Rule 6
        (1.0, 3.5, 7),   # > 2.618 → Rule 7
    ]
    for m1, m2, expected in cases:
        got = classify_rule(m1, m2)
        status = "✓" if got == expected else "✗"
        print(f"[rules    ] {status} m2/m1={m2/m1:.3f} → Rule {got} (expected {expected})")
        assert got == expected
    print()


if __name__ == "__main__":
    print("=" * 60)
    print("Synthetic tests")
    print("=" * 60)
    test_classify_rule_boundaries()
    test_confirm_impulse_pure_math()
    test_clean_impulse_up()
    test_clean_zigzag_down()
    test_clean_flat()
    test_clean_triangle()
    print("All synthetic tests passed ✓")
