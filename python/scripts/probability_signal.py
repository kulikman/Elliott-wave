"""Build one Probability Model v0 signal from the calibration artifact."""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ewb.research import build_probability_signal, load_probability_calibration


REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_CALIBRATION = os.path.join(
    REPO,
    "brain-output",
    "indicator-spec",
    "probability_calibration_v0.json",
)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fig-type", required=True, help="Detected figure type, e.g. flat")
    p.add_argument("--interval", required=True, help="Chart interval, e.g. 1h")
    p.add_argument("--direction", required=True, choices=["up", "down"], help="Figure direction")
    p.add_argument("--entry-px", type=float, default=None, help="Confirmed entry price")
    p.add_argument("--amplitude", type=float, default=None, help="Absolute figure amplitude")
    p.add_argument("--calibration", default=DEFAULT_CALIBRATION, help="Calibration JSON path")
    return p


def main() -> None:
    args = parser().parse_args()
    calibration = load_probability_calibration(args.calibration)
    signal = build_probability_signal(
        calibration,
        fig_type=args.fig_type,
        interval=args.interval,
        direction=args.direction,
        entry_px=args.entry_px,
        amplitude=args.amplitude,
    )
    print(json.dumps(signal, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
