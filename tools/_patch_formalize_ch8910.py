#!/usr/bin/env python3
"""Ручная формализация Гл.8-10 (in-session, без API). status=draft."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from tools._lib.aku_io import load_all_aku, save_aku

# id -> (status, applies_when, constraint, notes)
F = {
"AKU-0041": ("draft", "pattern == 'impulse'",
    "has_extension(impulse) == true AND alternation(wave_2, wave_4) == true", None),
"AKU-0042": ("draft", "pattern == 'impulse' AND degree == 'multiwave'",
    "count(is_polywave in [wave_1, wave_3, wave_5]) == 1 AND count(is_monowave in [wave_1, wave_3, wave_5]) == 2", None),
"AKU-0043": ("draft", "pattern == 'impulse' AND degree == 'multiwave'",
    "is_polywave(wave_2) OR is_polywave(wave_4)", None),
"AKU-0044": ("draft", "pattern == 'impulse' AND degree == 'multiwave'",
    "adjacent(longest_correction, extended_wave) AND (extended_wave==1 IMPLIES duration(wave_2) > duration(wave_4)) AND (extended_wave==5 IMPLIES duration(wave_4) > duration(wave_2))", None),
"AKU-0045": ("draft", "pattern == 'impulse' AND subtype != 'terminal'",
    "not (any odd_wave in [1,3,5] is_subdivided WHILE all corrective_waves in [2,4] are monowaves)",
    "Правило порядка сегментации (сложности). Требует отслеживания степени подразделения волн."),
"AKU-0046": ("draft", "pattern == 'impulse' AND subtype != 'terminal'",
    "is_subdivided(wave_1) IMPLIES is_subdivided(wave_2)", None),
"AKU-0047": ("draft", "pattern == 'x-wave'",
    "complexity(x_wave) >= complexity(preceding_c_wave) AND complexity(x_wave) <= max_complexity(standard_patterns_in_config)", None),
"AKU-0048": ("draft", "pattern == 'impulse' AND extended_wave == 1",
    "complexity(wave_2) > complexity(wave_4)", None),
"AKU-0049": ("draft", "pattern == 'impulse' AND extended_wave == 5",
    "complexity(wave_4) > complexity(wave_2) AND duration(wave_4) > duration(wave_2)", None),
"AKU-0050": ("draft", "pattern == 'impulse' AND length(wave_2) large_relative_to length(wave_1)",
    "is_subdivided(wave_2) AND not exceeds(end(wave_2.c), end(wave_2.a))",
    "'Слишком велика' связано с правилом волны-2 < 100% (AKU-0001); порог уточняется."),
"AKU-0051": ("draft", "subtype IN ('failure_5th', 'flat_failure_c', 'contracting_nonlimiting_triangle')",
    "extreme_point(pattern) != end_point(pattern)",
    "В 3 из 4 ситуаций потери силы импульса экстремум не совпадает с концом фигуры."),
"AKU-0052": ("draft", "pattern IN ('impulse', 'terminal_impulse', 'triangle')",
    "count(segments simultaneously touching both opposite_trendlines) <= 4",
    "Из 5 сегментов (6 возможных точек касания одного Порядка) одновременно касаться двух линий могут только 4."),
"AKU-0053": ("draft", "three consecutive adjacent waves of same degree",
    "not (duration(w_i) == duration(w_i+1) AND duration(w_i+1) == duration(w_i+2))", None),
"AKU-0054": ("draft", "pattern == 'impulse'",
    "not breaks(wave_3, trendline(end(2), end(4)))",
    "Если breaks(wave_5, trendline(2,4)) → фигура Терминальная."),
"AKU-0055": ("draft", "pattern IN corrective AND pattern != 'triangle'",
    "count(same_degree_points touching parallel_trendlines) <= 3",
    "4 возможные точки касания, но касаться параллельных линий могут только 3."),
"AKU-0056": ("not_formalizable", None, None,
    "Мета-правило об исключениях: в особых точках (завершение мультиволны+, b-волна, и т.д.) одно критическое правило может не выполняться. Используется как контекст для смягчения mandatory-проверок, не как constraint."),
"AKU-0058": ("not_formalizable", None, None,
    "Директива рабочего процесса (классифицировать все сегменты как :5/:3, придерживаться проверенной структуры). Не выражается как ценовой constraint."),
"AKU-0059": ("draft", "energy_rating(wave) IN [+1, +2, +3] AND direction(wave) == up",
    "not reaches(next_wave_same_degree, start_level(wave))",
    "Рейтинг Энергии определяется в Гл.10."),
"AKU-0060": ("draft", "pattern == 'terminal_impulse' AND position == 'post_pattern'",
    "reaches(next_move, start_level(terminal)) AND duration(until_reach) <= 0.5 * duration(terminal)", None),
"AKU-0061": ("draft", "pattern == 'triple_zigzag' AND parent IN ('flat', 'contracting_triangle')",
    "not reaches(next_wave_same_degree, start_level(triple_zigzag))", None),
"AKU-0062": ("draft", "pattern == 'triple_combination'",
    "type(correction_1) != 'triangle' AND type(correction_2) != 'triangle'",
    "correction_1 = начальная коррекция; correction_2 = коррекция сразу после первой x-волны."),
"AKU-0063": ("draft", "pattern == 'triple_combination'",
    "parent IN ('triangle', 'terminal_impulse')", None),
"AKU-0064": ("draft", "subtype == 'failure_c' AND position == 'post_pattern'",
    "reaches(next_wave_same_degree, start_level(pattern))", None),
"AKU-0065": ("draft", "subtype == 'irregular_failure' AND position == 'post_pattern'",
    "reaches(next_wave_same_degree, start_level(pattern))", None),
"AKU-0066": ("draft", "pattern == 'moving_correction' AND position == 'post_pattern'",
    "length(next_impulse) > 1.618 * length(previous_impulse) AND type(next) NOT IN ('double_three', 'triple_three')", None),
"AKU-0067": ("draft", "pattern == 'moving_double_three' AND position == 'post_pattern'",
    "type(next_wave) == 'impulse' AND length(next_wave) > 1.618 * length(previous_impulse)",
    "Подвижная Двойная Тройка может быть только волной-2."),
"AKU-0068": ("draft", "pattern == 'zigzag' AND subtype == 'elongated' AND position == 'post_pattern'",
    "not reaches(next_wave_same_degree, start_level(zigzag))", None),
"AKU-0069": ("draft", "pattern == 'expanding_triangle' AND position == 'post_pattern'",
    "length(thrust) < max_width(triangle)", None),
"AKU-0070": ("draft", "pattern == 'expanding_triangle' AND position == 'wave_b'",
    "next_structure_contains('failure_c') == true",
    "Предиктивное правило: Неудавшаяся-с неизбежна."),
"AKU-0071": ("draft", "pattern == 'limiting_expanding_triangle' AND position == 'post_pattern'",
    "not reaches(next_wave_same_degree, start_level(triangle))", None),
"AKU-0072": ("draft", "pattern == 'nonlimiting_expanding_triangle' AND is_last_phase(complex_correction) AND position == 'post_pattern'",
    "reaches(next_wave, start_level(triangle))", None),
"AKU-0073": ("draft", "pattern == 'trend_impulse' AND position == 'post_pattern' AND role NOT IN ('wave_5', 'wave_c')",
    "not reaches(next_wave, start_level(impulse))", None),
"AKU-0074": ("draft", "pattern == 'trend_impulse' AND role IN ('wave_a', 'wave_1', 'wave_3') AND position == 'post_pattern'",
    "retrace(next_wave) <= 0.618 * length(impulse)", None),
"AKU-0075": ("draft", "pattern == 'impulse' AND extended_wave == 3 AND position == 'post_pattern'",
    "extreme(retrace) reaches price_zone(wave_4)", None),
"AKU-0076": ("draft", "pattern == 'impulse' AND extended_wave == 5 AND position == 'post_pattern'",
    "length(next_wave_same_degree) > 0.618 * length(wave_5)",
    "Строгое '>' и независимо от роли Импульса (отличие от AKU-0034)."),
"AKU-0077": ("draft", "pattern == 'terminal_impulse' AND position == 'post_pattern'",
    "reaches(next_wave, start_level(terminal)) AND duration(until_reach) <= 0.5 * duration(terminal)",
    "Обычно достигается за ~25% времени формирования."),
"AKU-0078": ("draft", "pattern == 'terminal_impulse' AND position == 'post_pattern'",
    "hold(extreme(terminal)) for duration >= 2 * duration(terminal)",
    "'Примерно' два периода — мягкое ограничение."),
}

by_id = {a["id"]: a for a in load_all_aku()}
done = 0
for aku_id, (st, aw, cons, notes) in F.items():
    a = by_id.get(aku_id)
    if not a:
        print(f"  ПРОПУСК {aku_id}: не найден"); continue
    fp = a.pop("_filepath")
    a["formalization"] = {"status": st, "applies_when": aw, "constraint": cons, "formalization_notes": notes}
    save_aku(a, fp)
    done += 1
print(f"Формализовано: {done}/{len(F)} (not_formalizable: 2)")
