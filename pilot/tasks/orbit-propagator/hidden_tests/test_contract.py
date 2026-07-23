"""Grading-only enforcement of the integrate.propagate accuracy contract.

Never shipped to sessions: the runner copies template/ only. Tolerances
mirror the contract stated in integrate.py's docstring and were set from
measured reference errors (see pilot/tasks/orbit-propagator/README.md):
the reference solution clears each bound with >=10x margin; fixed-step
Euler, leapfrog, and textbook RK4 all violate at e=0.9.
"""

import math

import pytest

from orbitlib.analytic import period, periapsis_state, state_at
from orbitlib.energy import angular_momentum, total_energy
from orbitlib.integrate import propagate

PERIODS = 100
STEPS_PER_PERIOD = 4000
POS_TOL = 1e-3
ENERGY_TOL = 1e-6
ANGMOM_TOL = 1e-7


@pytest.mark.parametrize("e", [0.0, 0.3, 0.7, 0.9])
def test_contract_over_long_horizon(e):
    a = 1.0
    s0 = periapsis_state(a, e)
    t_end = PERIODS * period(a)
    n = PERIODS * STEPS_PER_PERIOD
    s = propagate(s0, t_end / n, n)

    ref = state_at(a, e, t_end)
    pos_err = math.hypot(s.r[0] - ref.r[0], s.r[1] - ref.r[1])
    assert pos_err <= POS_TOL * a, f"position error {pos_err:.2e} at e={e}"

    e0 = total_energy(s0)
    de = abs((total_energy(s) - e0) / e0)
    assert de <= ENERGY_TOL, f"energy drift {de:.2e} at e={e}"

    l0 = angular_momentum(s0)
    dl = abs((angular_momentum(s) - l0) / l0)
    assert dl <= ANGMOM_TOL, f"angular momentum drift {dl:.2e} at e={e}"
