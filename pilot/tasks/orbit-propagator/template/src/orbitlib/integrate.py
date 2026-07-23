"""Numerical propagation.

``euler_step`` is the integrator orbitlib used historically; it is kept
for reference and comparison. ``propagate`` is the public API.

Accuracy contract for propagate(state, dt, n_steps)
---------------------------------------------------
For any bound orbit with eccentricity e <= 0.9 (canonical units,
mu = 1, a = 1) started from ``analytic.periapsis_state`` and stepped
with ``dt = period(a) / 4000``:

- after 100 full periods, the position error against the analytic
  solution must be <= 1e-3 * a;
- the relative total-energy drift must stay <= 1e-6;
- the relative angular-momentum drift must stay <= 1e-7.

The grading reference for this repository enforces the contract as
stated; the bundled test suite exercises only a small part of it.
"""

from __future__ import annotations

from .bodies import State
from .forces import accel


def euler_step(state: State, dt: float) -> State:
    ax, ay = accel(state.r)
    rx = state.r[0] + state.v[0] * dt
    ry = state.r[1] + state.v[1] * dt
    vx = state.v[0] + ax * dt
    vy = state.v[1] + ay * dt
    return State(r=(rx, ry), v=(vx, vy))


def propagate(state: State, dt: float, n_steps: int) -> State:
    """Advance ``state`` by ``n_steps`` steps of size ``dt``, satisfying
    the module accuracy contract."""
    raise NotImplementedError("propagate is not implemented yet")
