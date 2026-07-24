"""Reference solution (grading/calibration only, never shipped). Uses the
cancellation-avoiding formula (Numerical Recipes): compute the root whose
sign does not cancel, then get the other from the product c/a."""

from __future__ import annotations

import math


def roots(a: float, b: float, c: float) -> tuple[float, float]:
    disc = math.sqrt(b * b - 4 * a * c)
    if b >= 0:
        q = -(b + disc) / 2
    else:
        q = -(b - disc) / 2
    r1 = q / a
    r2 = (c / q) if q != 0 else r1
    return tuple(sorted((r1, r2)))
