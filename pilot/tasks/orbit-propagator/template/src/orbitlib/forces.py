"""Central gravity in canonical units."""

from __future__ import annotations

import math

MU = 1.0  # gravitational parameter G*M


def accel(r: tuple[float, float]) -> tuple[float, float]:
    d = math.hypot(r[0], r[1])
    k = -MU / (d * d * d)
    return (k * r[0], k * r[1])
