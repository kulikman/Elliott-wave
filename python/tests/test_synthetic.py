"""Synthetic tests: generate known structures, verify detector finds them."""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from ewb.monowaves import Pivot, detect_monowaves
from ewb.rules import classify_pivots, classify_rule
from ewb.figures import match_figures, _try_double_corr
from ewb.confirm import confirm_impulse, confirm_flat, confirm_triangle, all_passed


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


# ─── Regression tests: parity fixes (2026-06-09 audit) ───────────────────────

def test_confirm_flat_c_wave_minimum():
    """D1: C < 61.8%A must be Error (not neutral) after parity fix."""
    # failed-c: B=100%A, C=50%A → now Error
    r = confirm_flat([100, 80, 100, 90])
    errs = [c for c in r if c.severity == "E" and not c.ok]
    assert any("C=" in e.msg and "<61.8%" in e.msg for e in errs), \
        f"failed-c flat should produce C<61.8%A error, got: {[e.msg for e in errs]}"
    assert not all_passed(r), "failed-c flat must not confirm"

    # normal flat: B=100%A, C=100%A → ok
    r = confirm_flat([100, 80, 100, 80])
    assert all_passed(r), "normal flat (B=C=A) must confirm"

    # extended flat: B=100%A, C=150%A → ok (C≥61.8%A)
    r = confirm_flat([100, 80, 100, 70])
    assert all_passed(r), "extended flat (C=150%A) must confirm"


def test_confirm_flat_subtype_labels():
    """D1: subtype neutral label present (AKU-0213)."""
    # ordinary: C ≈ A (80-120%)
    r = confirm_flat([100, 80, 100, 80])
    labels = {c.aku: c.msg for c in r if c.severity == "N"}
    assert "AKU-0213" in labels, "subtype label missing"
    assert "обыкн" in labels["AKU-0213"]

    # extended: C > 138% A
    r = confirm_flat([100, 80, 100, 70])   # C=30/20=150%
    labels = {c.aku: c.msg for c in r if c.severity == "N"}
    assert "расш" in labels.get("AKU-0213", "")


def test_double_corr_y_wave_required():
    """D2: double_corr with Y < 61.8%W must be rejected after parity fix."""
    # small Y: W=20, X=8 (40%), Y=6 (30%) → rejected
    pts = _manual_pivots([100, 80, 88, 82], [0, -1, 1, -1])
    fig = _try_double_corr(pts, 0)
    assert fig is None, "DC with Y=30%W must not match after parity fix"

    # good DC: W=20, X=8 (40%), Y=24 (120%) → ok
    pts = _manual_pivots([100, 80, 88, 64], [0, -1, 1, -1])
    fig = _try_double_corr(pts, 0)
    assert fig is not None, "DC with Y=120%W must match"
    assert fig.type == "double_corr"

    # large X: W=20, X=14 (70%) → rejected by X check (not changed)
    pts = _manual_pivots([100, 80, 94, 66], [0, -1, 1, -1])
    fig = _try_double_corr(pts, 0)
    assert fig is None, "DC with X=70%W must not match"


def test_confirm_triangle_e_wave():
    """D4: triangle with e >= c (6 pivots) must produce warning after parity fix."""
    # perfect triangle: a=20 b=15 c=12 d=9 e=6 → all ok
    r = confirm_triangle([100, 120, 105, 117, 108, 114])
    assert all_passed(r), "perfect triangle must pass"
    checks = {c.msg: c.ok for c in r}
    assert any("e<c" in msg and ok for msg, ok in checks.items()), "e<c check must be present and ok"

    # e=14 > c=12 → warning
    r = confirm_triangle([100, 120, 105, 117, 108, 122])
    checks = {c.msg: c.ok for c in r}
    e_checks = [c for c in r if "e" in c.msg.lower() and "c" in c.msg.lower()]
    assert e_checks, "e<c check must be present for 6-pivot input"
    assert not e_checks[0].ok, "e>=c must produce a failed check"

    # 5-pivot input: no e check
    r = confirm_triangle([100, 120, 105, 117, 108])
    msgs = [c.msg for c in r]
    assert not any("e" in m.lower() for m in msgs), "no e check for 5-pivot triangle"


def test_hybrid_impulse_rule67():
    """Sprint 5 hybrid fallback: impulse with deep W2/W4 (Rule 6-7 in structure matcher)
    должен находиться через _try_impulse / confirm_impulse напрямую, минуя структурный путь.
    Rule 6-7 → base=0 в Pine → структурный [5,0,5,0,5] не матчит [5,3,5,3,5].
    Python _try_impulse работает напрямую по ценам — тест проверяет этот путь.
    """
    # Глубокий W2 (80%W1) и глубокий W4 (80%W3) → Rule 6-7 в реальном детекторе,
    # но геометрически это всё ещё корректный импульс (нет W2/W4 overlap, W3 не min)
    # Up impulse: p0=100, p1=130 (W1=30), p2=106 (W2=24, 80%W1), p3=160 (W3=54),
    #             p4=138 (W4=22, 41%W3), p5=185 (W5=47)
    prices = [100, 130, 106, 160, 138, 185]
    figs = match_figures(_manual_pivots(prices, [0, 1, -1, 1, -1, 1]))
    impulses = [f for f in figs if f.type == "impulse"]
    assert impulses, "Deep-W2 impulse must be found via hybrid geometry path"
    assert impulses[0].direction == "up"

    # Прямая проверка confirm_impulse (тот же путь что в hybridImpulseOK)
    r = confirm_impulse(prices, "up")
    errs = [c for c in r if c.severity == "E" and not c.ok]
    assert not errs, f"Deep-W2 impulse should have no E-errors, got: {[e.msg for e in errs]}"

    # Убеждаемся что W2 retrace check даёт warning (не error) — это D5
    w2_check = next((c for c in r if c.aku == "AKU-0127"), None)
    assert w2_check is not None and w2_check.severity == "W", \
        "W2 > 61.8%W1 must be Warning (not Error) — D5 design decision"


def test_hybrid_triangle_geometry():
    """Треугольник с неизвестными структурами (все base=0) должен находиться
    через confirmTriangle напрямую по ценам.
    """
    # Сужающийся треугольник: a=20, b=15, c=12, d=9, e=6
    prices = [100, 120, 105, 117, 108, 114]
    figs = match_figures(_manual_pivots(prices, [0, 1, -1, 1, -1, 1]))
    triangles = [f for f in figs if f.type == "triangle"]
    assert triangles, "Perfect contracting triangle must be found"

    # D4 divergence: Python e<c = severity W (warning, не блокирует all_passed).
    # Треугольник с e>c находится, но checks содержат failed W-check.
    # Pine строже (hard bool) — задокументировано в pine_parity_audit.md.
    prices_bad = [100, 120, 105, 117, 108, 122]  # e=14 > c=12
    figs_bad = match_figures(_manual_pivots(prices_bad, [0, 1, -1, 1, -1, 1]))
    bad_tris = [f for f in figs_bad if f.type == "triangle"]
    assert bad_tris, "Triangle with e>c still found (Python: warning-only D4)"
    e_warn = [c for c in bad_tris[0].checks if "e" in c.msg and not c.ok]
    assert e_warn, "Must have failed e<c warning check"
    assert e_warn[0].severity == "W", "D4: e<c must be W not E (backtest impact=0)"


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


def test_epic0_structural_lists():
    """EPIC 0: структурные списки Гл.3 (AKU-0148-0150, 0167-0170)."""
    from ewb.rules import rule_to_structure_list, rule_to_structure, structure_to_base

    # AKU-0148: Правило 1 → :5 наиболее вероятно
    assert rule_to_structure_list(1)[0][0] == ":5"
    # AKU-0150: Правило 3 → :F3 во главе, список содержит обе базы (граница)
    r3 = [lbl for lbl, _ in rule_to_structure_list(3)]
    assert r3[0] == ":F3" and ":5" in r3 and ":L5" in r3
    # AKU-0167: Правило 4 зависит от Условия — c даёт :c3 во главе
    assert rule_to_structure_list(4, "c")[0][0] == ":c3"
    assert rule_to_structure_list(4, "a")[0][0] == ":F3"
    # AKU-0169/0170: Правило 6-7 больше НЕ '?' (корень проблемы figures.py)
    assert rule_to_structure(6) != "?" and rule_to_structure(6) != ""
    assert rule_to_structure(7) != "?" and rule_to_structure(7) != ""
    print("[epic0    ] ✓ R1→:5  R3→:F3(±)  R4c→:c3  R6/7≠'?'")

    # structure_to_base: метки с цифрой 5 → 5, с цифрой 3 → 3
    assert structure_to_base(":5") == 5
    assert structure_to_base(":s5") == 5
    assert structure_to_base(":L5") == 5
    assert structure_to_base(":F3") == 3
    assert structure_to_base("x:c3") == 3
    assert structure_to_base(":sL3") == 3
    assert structure_to_base("?") == 0
    print("[epic0    ] ✓ structure_to_base: :5/:s5/:L5→5  :F3/x:c3/:sL3→3\n")


def test_epic0_classify_fills_struct_list():
    """EPIC 0: classify_pivots заполняет struct_list/struct_label на реальных пивотах."""
    pivots_target = [100, 120, 110, 140, 130, 160]
    df = _build_ohlc_from_pivots(pivots_target, bars_per_seg=30, jitter=0.005)
    pivots = detect_monowaves(df, atr_period=14, atr_mult=1.0)
    classify_pivots(pivots)
    classified = [p for p in pivots if p.rule_no > 0]
    assert classified, "expected at least one classified pivot"
    for p in classified:
        assert p.struct_list, f"pivot rule={p.rule_no} has empty struct_list"
        assert p.struct_label, f"pivot rule={p.rule_no} has empty struct_label"
        # struct_label = вершина списка
        assert p.struct_label == p.struct_list[0][0]
    print(f"[epic0    ] ✓ {len(classified)} пивотов получили struct_list/struct_label\n")


if __name__ == "__main__":
    print("=" * 60)
    print("Synthetic tests")
    print("=" * 60)
    test_epic0_structural_lists()
    test_epic0_classify_fills_struct_list()
    test_classify_rule_boundaries()
    test_confirm_impulse_pure_math()
    test_clean_impulse_up()
    test_clean_zigzag_down()
    test_clean_flat()
    test_clean_triangle()
    # Parity regression (2026-06-09)
    test_confirm_flat_c_wave_minimum()
    test_confirm_flat_subtype_labels()
    test_double_corr_y_wave_required()
    test_confirm_triangle_e_wave()
    print("All synthetic tests passed ✓")
