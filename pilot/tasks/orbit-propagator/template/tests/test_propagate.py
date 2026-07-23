import math

from orbitlib.analytic import period, periapsis_state, state_at
from orbitlib.energy import total_energy
from orbitlib.integrate import propagate


def _pos_error(s, ref):
    return math.hypot(s.r[0] - ref.r[0], s.r[1] - ref.r[1])


def test_circular_orbit_one_period():
    a = 1.0
    s0 = periapsis_state(a, 0.0)
    n = 2000
    s = propagate(s0, period(a) / n, n)
    assert _pos_error(s, s0) <= 1e-3 * a
    assert abs((total_energy(s) - total_energy(s0)) / total_energy(s0)) <= 1e-6


def test_elliptic_orbit_one_period():
    a, e = 1.0, 0.3
    s0 = periapsis_state(a, e)
    n = 4000
    s = propagate(s0, period(a) / n, n)
    ref = state_at(a, e, period(a))
    assert _pos_error(s, ref) <= 1e-3 * a
