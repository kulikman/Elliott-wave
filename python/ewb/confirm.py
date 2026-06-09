"""Pattern confirmation rules (Neely Гл.5-6).

Each function returns (passed: bool, reason: str). Reason carries severity
prefix matching ewb_confirm.pine convention: O:/E:/W:/N:.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class CheckResult:
    ok: bool
    severity: str   # "O" ok, "E" error, "W" warning, "N" neutral
    msg: str
    aku: str


# ─────────── IMPULSE (AKU-0001..0009, 0126/0127, 0203) ──────────

def imp_w2_no_overlap(p0: float, p2: float, direction: str) -> CheckResult:
    """AKU-0001/0004: W2 cannot reach start of W1."""
    ok = p2 > p0 if direction == "up" else p2 < p0
    return CheckResult(ok, "O" if ok else "E",
        "W2 > W1start" if ok else "W2 пробила W1start", "AKU-0001")


def imp_w4_no_overlap(p2: float, p4: float, direction: str) -> CheckResult:
    """AKU-0005: W4 cannot reach start of W3 (= end of W2)."""
    ok = p4 > p2 if direction == "up" else p4 < p2
    return CheckResult(ok, "O" if ok else "E",
        "W4 > W3start" if ok else "W4 пробила W3start", "AKU-0005")


def imp_w3_not_shortest(w1: float, w3: float, w5: float | None = None) -> CheckResult:
    """AKU-0002/0007: W3 must not be the shortest of W1/W3/W5."""
    if w5 is not None:
        ok = not (w3 < w1 and w3 < w5)
    else:
        ok = w3 >= w1
    # AKU-0002 дословно: «если W3 короче обеих — счёт НЕВЕРЕН» → кардинальное (E),
    # не warning. Консистентно с Pine confirmImpulse (r3 в обязательном ok).
    return CheckResult(ok, "O" if ok else "E",
        "W3 не самая короткая" if ok else "W3 самая короткая (счёт неверен)", "AKU-0002")


def imp_w2_retrace(w1: float, w2: float) -> CheckResult:
    """AKU-0127: W2 retraces ≤ 61.8% of W1."""
    if w1 <= 0:
        return CheckResult(True, "N", "W1=0", "AKU-0127")
    r = w2 / w1
    ok = r <= 0.618
    return CheckResult(ok, "O" if ok else "W",
        f"W2={r*100:.1f}%≤61.8%" if ok else f"W2={r*100:.1f}%>61.8%", "AKU-0127")


def imp_alternation(w2: float, w4: float) -> CheckResult:
    """AKU-0126: W2/W4 must alternate (different by >20%)."""
    if w2 <= 0:
        return CheckResult(True, "N", "W2=0", "AKU-0126")
    r = w4 / w2
    ok = r < 0.8 or r > 1.2
    return CheckResult(ok, "O" if ok else "W",
        f"Черед. r={r:.2f}" if ok else "W2≈W4 нет черед.", "AKU-0126")


def imp_w2_w4_no_overlap(p1: float, p2: float, p3: float, p4: float) -> CheckResult:
    """AKU-0009: Price ranges of W2 and W4 must not overlap (Trending Impulse)."""
    w2lo, w2hi = min(p1, p2), max(p1, p2)
    w4lo, w4hi = min(p3, p4), max(p3, p4)
    ok = w2hi < w4lo or w4hi < w2lo
    return CheckResult(ok, "O" if ok else "E",
        "W2/W4 нет перекр." if ok else "W2/W4 перекрыв.", "AKU-0009")


def imp_w5_length(w4: float, w5: float) -> CheckResult:
    """AKU-0006: W5 ≥ 38.2% W4 (else Failed 5th)."""
    if w4 <= 0:
        return CheckResult(True, "N", "W4=0", "AKU-0006")
    r = w5 / w4
    ok = r >= 0.382
    return CheckResult(ok, "O" if ok else "W",
        f"W5={r*100:.0f}%≥38.2%" if ok else f"W5={r*100:.0f}%<38.2% (Failed?)", "AKU-0006")


def imp_no_three_equal(w1: float, w3: float, w5: float) -> CheckResult:
    """AKU-0203: W1≈W3≈W5 (within 15%) → wrong starting point."""
    mn = min(w1, w3, w5)
    mx = max(w1, w3, w5)
    if mx <= 0:
        return CheckResult(True, "N", "", "AKU-0203")
    ok = mn / mx < 0.85
    return CheckResult(ok, "O" if ok else "W",
        "W1/W3/W5 различимы" if ok else "W1≈W3≈W5 неверный старт?", "AKU-0203")


def confirm_impulse(prices: list[float], direction: str) -> list[CheckResult]:
    """Run all impulse checks. prices = [p0..p5] (6 pivots = 5 waves)."""
    assert len(prices) >= 5, "need ≥5 pivots"
    p0, p1, p2, p3, p4 = prices[:5]
    p5 = prices[5] if len(prices) >= 6 else None
    w1 = abs(p1 - p0); w2 = abs(p2 - p1)
    w3 = abs(p3 - p2); w4 = abs(p4 - p3)
    w5 = abs(p5 - p4) if p5 is not None else None
    results = [
        imp_w2_no_overlap(p0, p2, direction),
        imp_w4_no_overlap(p2, p4, direction),
        imp_w3_not_shortest(w1, w3, w5),
        imp_w2_retrace(w1, w2),
        imp_alternation(w2, w4),
        imp_w2_w4_no_overlap(p1, p2, p3, p4),
    ]
    if w5 is not None:
        results.append(imp_w5_length(w4, w5))
        results.append(imp_no_three_equal(w1, w3, w5))
    return results


# ─────────── ZIGZAG (AKU-0014/0022) ──────────

def confirm_zigzag(prices: list[float]) -> list[CheckResult]:
    """Zigzag = 5-3-5. prices = [p0,p1,p2,p3] (A=p0→p1, B=p1→p2, C=p2→p3)."""
    assert len(prices) >= 4
    a = abs(prices[1] - prices[0])
    b = abs(prices[2] - prices[1])
    c = abs(prices[3] - prices[2])
    results = []
    # AKU-0014: B ≤ A
    ok = b <= a
    results.append(CheckResult(ok, "O" if ok else "E",
        "B≤A" if ok else "B>A невозм.", "AKU-0014"))
    # AKU-0022: C ≥ 61.8% A
    if a > 0:
        r = c / a
        ok = r >= 0.618
        results.append(CheckResult(ok, "O" if ok else "W",
            f"C={r*100:.0f}%≥61.8%A" if ok else f"C={r*100:.0f}%<61.8%A", "AKU-0022"))
    return results


# ─────────── FLAT (AKU-0017/0025) ──────────

def confirm_flat(prices: list[float]) -> list[CheckResult]:
    """Flat = 3-3-5. prices = [p0,p1,p2,p3] (A=p0→p1, B=p1→p2, C=p2→p3)."""
    assert len(prices) >= 4
    a = abs(prices[1] - prices[0])
    b = abs(prices[2] - prices[1])
    c = abs(prices[3] - prices[2])
    results = []
    # AKU-0017: B ≥ 61.8% A
    if a > 0:
        r = b / a
        ok = r >= 0.618
        results.append(CheckResult(ok, "O" if ok else "E",
            f"B={r*100:.0f}%≥61.8%A" if ok else f"B={r*100:.0f}%<61.8%A", "AKU-0017"))
    # Neely Гл.5: C ≥ 61.8%A (минимальный порог, как в Pine confirmFlat)
    # Дополнительно: C ≈ A (80-120%) — нейтральная инфо-метка о подтипе
    if a > 0:
        r = c / a
        c_min_ok = r >= 0.618
        results.append(CheckResult(c_min_ok, "O" if c_min_ok else "E",
            f"C={r*100:.0f}%≥61.8%A" if c_min_ok else f"C={r*100:.0f}%<61.8%A", "AKU-0025"))
        # Subtype info (neutral)
        c_approx_ok = 0.8 <= r <= 1.2
        results.append(CheckResult(c_approx_ok, "N",
            f"C≈A обыкн." if c_approx_ok else ("C>138%A расш." if r > 1.382 else "C<80%A неуд-с"), "AKU-0213"))
    return results


# ─────────── TRIANGLE (AKU-0018) ──────────

def confirm_triangle(prices: list[float]) -> list[CheckResult]:
    """Triangle = 3-3-3-3-3. prices = [p0..p5], waves a,b,c,d,e.
    При len>=6 также проверяет e < c (как Pine confirmTriangle при n>=6).
    """
    assert len(prices) >= 5
    w1 = abs(prices[1] - prices[0])
    w2 = abs(prices[2] - prices[1])
    w3 = abs(prices[3] - prices[2])
    w4 = abs(prices[4] - prices[3])
    ok_cd = w3 < w1 and w4 < w2
    results = [CheckResult(ok_cd, "O" if ok_cd else "W",
        "c<a, d<b сужается" if ok_cd else
        f"Не сужается c/a={w3/w1 if w1>0 else 0:.2f} d/b={w4/w2 if w2>0 else 0:.2f}", "AKU-0018")]
    if len(prices) >= 6:
        w5 = abs(prices[5] - prices[4])
        ok_e = w5 < w3
        results.append(CheckResult(ok_e, "O" if ok_e else "W",
            f"e<c e/c={w5/w3 if w3>0 else 0:.2f}" if ok_e else
            f"e≥c e/c={w5/w3 if w3>0 else 0:.2f}", "AKU-0018"))
    return results


def all_passed(results: list[CheckResult]) -> bool:
    """True if no Error-severity check failed (warnings OK)."""
    return all(r.ok or r.severity != "E" for r in results)
