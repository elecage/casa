"""Conserved quantities of the two-body problem.

For any exact solution both quantities are constants of motion; how well
a numerical propagator preserves them is the standard measure of its
long-horizon quality.
"""

from __future__ import annotations

import math

from .bodies import State
from .forces import MU


def total_energy(s: State) -> float:
    speed_sq = s.v[0] ** 2 + s.v[1] ** 2
    return 0.5 * speed_sq - MU / math.hypot(s.r[0], s.r[1])


def angular_momentum(s: State) -> float:
    return s.r[0] * s.v[1] - s.r[1] * s.v[0]
