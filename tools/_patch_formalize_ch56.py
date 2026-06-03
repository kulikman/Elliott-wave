#!/usr/bin/env python3
"""Ручная формализация Гл.5-6 (in-session, без API). status=draft для проверки Антоном."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from tools._lib.aku_io import load_all_aku, save_aku

# id -> (applies_when, constraint, notes|None)
F = {
"AKU-0017": (
    "pattern == 'flat' AND length(wave_b) > 1.382 * length(wave_a)",
    "not exceeds(end(wave_c), start_level(wave_b))",
    "start_level(wave_b) = конец волны-a. Касается только Плоской, не Треугольника."),
"AKU-0018": (
    "pattern == 'triangle'",
    "segment_count == 5 AND labels(segments) == ['a','b','c','d','e']",
    None),
"AKU-0019": (
    "pattern == 'triangle'",
    "for seg in [a,b,c,d,e]: structure(seg) == ':3'",
    None),
"AKU-0020": (
    "pattern == 'triangle'",
    "not breaks(wave_c, trendline(end(b), end(d))) AND not breaks(wave_e, trendline(end(b), end(d)))",
    "Линия b-d — Базовая линия Треугольника. 'Общее правило' — редкие исключения возможны."),
"AKU-0021": (
    "pattern == 'expanding_triangle'",
    "position NOT IN {zigzag.wave_b, triangle.wave_b, triangle.wave_c, triangle.wave_d}",
    None),
"AKU-0022": (
    "pattern == 'zigzag' AND subtype == 'truncated'",
    "0.382 * length(wave_a) <= length(wave_c) AND length(wave_c) < 0.618 * length(wave_a)",
    None),
"AKU-0023": (
    "pattern == 'zigzag' AND subtype == 'elongated' AND position == 'post_pattern'",
    "retrace(next_wave) > 0.618 * length(wave_c) BEFORE price passes end(wave_c)",
    "Подтверждающее правило: если не выполнено — вероятно это Импульс, а не Зигзаг."),
"AKU-0024": (
    "pattern == 'zigzag'",
    "not touches(wave_c, parallel_line(through=end(wave_a), parallel_to=trendline(start(0), end(B))))",
    "Касание параллельной линии → зигзаг есть часть более сложной Коррекции."),
"AKU-0025": (
    "pattern == 'flat' AND b_type == 'normal'",
    "length(wave_c) >= 0.382 * length(wave_a)",
    "Минимальный предел волны-c в нормальной Плоской."),
"AKU-0026": (
    "pattern == 'flat' AND end_level(wave_b) beyond start_level(wave_a)",
    "length(wave_b) < 1.618 * length(wave_a) AND length(wave_b) != 1.382 * length(wave_a) AND length(wave_b) != 1.618 * length(wave_a)",
    "'Обычно' — мягкое ограничение. b приближается к 138.2%/161.8%, но не достигает их точно."),
"AKU-0027": (
    "pattern == 'contracting_triangle'",
    "has_fibonacci_ratio(among_segments) == true",
    "Требует определения 'fib-соотношение между сегментами' на уровне распознавания."),
"AKU-0028": (
    "pattern == 'triangle'",
    "length(wave_b) != 0.618 * length(wave_a)",
    "Если b == 61.8% a → отвергнуть гипотезу Треугольника (вероятностное, не абсолютное)."),
"AKU-0029": (
    "pattern == 'zigzag'",
    "length(wave_b) <= 0.618 * length(wave_a) AND length(wave_b) != length(wave_a)",
    None),
"AKU-0030": (
    "pattern == 'expanding_triangle' AND position == 'post_pattern_thrust'",
    "length(thrust) < length(wave_e)",
    "Выброс из Расширяющегося Треугольника не может превышать ширину (волну-e)."),
"AKU-0031": (
    "pattern == 'impulse' AND position == 'post_pattern'",
    "duration(until_break(trendline(end(2), end(4)))) <= duration(wave_5)",
    "Первое подтверждение импульса. Иначе: волна-5 терминальная, либо волна-4 не завершена, либо не импульс."),
"AKU-0032": (
    "pattern == 'impulse' AND extended_wave == 1 AND position == 'post_pattern'",
    "extreme(next_wave) reaches price(end(wave_4))",
    None),
"AKU-0033": (
    "pattern == 'impulse' AND extended_wave == 3 AND position == 'post_pattern'",
    "extreme(next_wave) within price_range(start(wave_4), end(wave_4))",
    "Обычно завершается вблизи конца волны-4."),
"AKU-0034": (
    "pattern == 'impulse' AND extended_wave == 5 AND position == 'post_pattern'",
    "length(next_corrective) >= 0.618 * length(wave_5)",
    "Доп. условие: length(next_corrective) < length(wave_5), если тренд силён."),
"AKU-0035": (
    "pattern == 'impulse' AND subtype == 'failure_5th' AND position == 'post_pattern'",
    "length(next_wave) >= length(whole_impulse) AND no_new_extreme(before reaching start_level(impulse))",
    None),
"AKU-0036": (
    "pattern IN ('flat','zigzag') AND length(wave_b) < length(wave_a) AND position == 'post_pattern'",
    "duration(until_break(trendline(start(0), end(B)))) <= duration(wave_c)",
    "Иначе: волна-c терминальная, либо 4-я волна не завершена, либо интерпретация ошибочна."),
"AKU-0038": (
    "pattern == 'contracting_triangle' AND position == 'post_pattern_stage1'",
    "breaks(next_wave, trendline(end(B), end(D))) AND duration(until_break) <= duration(wave_e)",
    None),
"AKU-0039": (
    "pattern == 'contracting_triangle' AND position == 'post_pattern_stage2'",
    "new_extreme(thrust) beyond extreme(triangle) AND duration(thrust) < 0.5 * duration(triangle)",
    "50%-е временное правило не применяется к Неограничивающим Треугольникам."),
"AKU-0040": (
    "pattern == 'moving_correction' AND position == 'post_pattern'",
    "length(next_wave) >= 1.618 * length(preceding_wave_or_group)",
    "Первая волна после Подвижной Коррекции должна быть взрывной."),
}

by_id = {a["id"]: a for a in load_all_aku()}
done = 0
for aku_id, (aw, cons, notes) in F.items():
    a = by_id.get(aku_id)
    if not a:
        print(f"  ПРОПУСК {aku_id}: не найден"); continue
    fp = a.pop("_filepath")
    a["formalization"] = {
        "status": "draft",
        "applies_when": aw,
        "constraint": cons,
        "formalization_notes": notes,
    }
    save_aku(a, fp)
    done += 1
print(f"Формализовано: {done}/{len(F)}")
