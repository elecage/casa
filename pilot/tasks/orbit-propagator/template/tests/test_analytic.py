import math

from orbitlib.analytic import period, periapsis_state, state_at
from orbitlib.energy import total_energy


def test_period_formula():
    assert math.isclose(period(1.0), 2.0 * math.pi, rel_tol=1e-12)


def test_periapsis_state_is_bound():
    s = periapsis_state(1.0, 0.5)
    assert total_energy(s) < 0


def test_state_at_zero_matches_periapsis():
    s0 = periapsis_state(1.0, 0.7)
    s = state_at(1.0, 0.7, 0.0)
    assert math.isclose(s.r[0], s0.r[0], abs_tol=1e-12)
    assert math.isclose(s.v[1], s0.v[1], abs_tol=1e-12)
