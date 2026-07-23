"""Closed-form Kepler solution for bound orbits (0 <= e < 1).

Orbits start at periapsis on the +x axis at t = 0. This module is exact
(up to float precision) and serves as the ground truth for validating
any numerical propagator.
"""

from __future__ import annotations

import math

from .bodies import State
from .forces import MU


def period(a: float) -> float:
    return 2.0 * math.pi * math.sqrt(a ** 3 / MU)


def periapsis_state(a: float, e: float) -> State:
    rp = a * (1.0 - e)
    vp = math.sqrt(MU * (1.0 + e) / rp)
    return State(r=(rp, 0.0), v=(0.0, vp))


def _solve_kepler(mean_anomaly: float, e: float) -> float:
    """Newton iteration for E - e*sin(E) = M."""
    m = math.fmod(mean_anomaly, 2.0 * math.pi)
    ecc_anomaly = m if e < 0.8 else math.pi
    for _ in range(50):
        f = ecc_anomaly - e * math.sin(ecc_anomaly) - m
        step = f / (1.0 - e * math.cos(ecc_anomaly))
        ecc_anomaly -= step
        if abs(step) < 1e-14:
            break
    return ecc_anomaly


def state_at(a: float, e: float, t: float) -> State:
    n = math.sqrt(MU / a ** 3)
    big_e = _solve_kepler(n * t, e)
    cos_e, sin_e = math.cos(big_e), math.sin(big_e)
    x = a * (cos_e - e)
    y = a * math.sqrt(1.0 - e * e) * sin_e
    factor = n * a / (1.0 - e * cos_e)
    vx = -factor * sin_e
    vy = factor * math.sqrt(1.0 - e * e) * cos_e
    return State(r=(x, y), v=(vx, vy))
