"""Trade execution helpers shared by research backtests."""
from __future__ import annotations


def exit_for_trade(high, low, close, entry_idx: int, entry_px: float,
                   side: int, exit_bars: int, amp: float,
                   use_tp_sl: bool = True) -> tuple[int, float, str]:
    """Return first TP/SL/time exit for a long (+1) or short (-1) trade."""
    n = len(close)
    if use_tp_sl and amp > 0:
        if side == +1:
            tp_px = entry_px + amp
            sl_px = entry_px - amp
        else:
            tp_px = entry_px - amp
            sl_px = entry_px + amp
    else:
        tp_px = sl_px = None

    for k in range(1, exit_bars + 1):
        bi = entry_idx + k
        if bi >= n:
            break
        hi, lo = high[bi], low[bi]
        if tp_px is not None:
            if side == +1:
                if lo <= sl_px:
                    return bi, sl_px, "sl"
                if hi >= tp_px:
                    return bi, tp_px, "tp"
            else:
                if hi >= sl_px:
                    return bi, sl_px, "sl"
                if lo <= tp_px:
                    return bi, tp_px, "tp"

    exit_idx = entry_idx + exit_bars
    return exit_idx, close[exit_idx], "time"
