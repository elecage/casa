"""The naive textbook quadratic formula (calibration only, never shipped).
The obvious implementation everyone writes; it catastrophically cancels
for the root where -b and sqrt(disc) nearly annihilate (|b| huge relative
to a, c). Passes the well-conditioned visible tests, fails the precision
contract on the hidden ill-conditioned cases — the invariant the
calibration test pins."""

from __future__ import annotations

import math


def roots(a: float, b: float, c: float) -> tuple[float, float]:
    disc = math.sqrt(b * b - 4 * a * c)
    r1 = (-b - disc) / (2 * a)
    r2 = (-b + disc) / (2 * a)
    return tuple(sorted((r1, r2)))
