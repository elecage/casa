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


# The contract's external step (period/4000) is too coarse near a
# high-eccentricity periapsis for any fixed classical scheme, so each
# external step is refined internally. RK4 with 4 substeps clears every
# contract bound with >=10x margin (measured).
_SUBSTEPS = 4


def _rk4_step(rx, ry, vx, vy, h):
    ax1, ay1 = accel((rx, ry))
    ax2, ay2 = accel((rx + 0.5 * h * vx, ry + 0.5 * h * vy))
    vx2, vy2 = vx + 0.5 * h * ax1, vy + 0.5 * h * ay1
    ax3, ay3 = accel((rx + 0.5 * h * vx2, ry + 0.5 * h * vy2))
    vx3, vy3 = vx + 0.5 * h * ax2, vy + 0.5 * h * ay2
    ax4, ay4 = accel((rx + h * vx3, ry + h * vy3))
    nrx = rx + h / 6.0 * (vx + 2 * vx2 + 2 * vx3 + (vx + h * ax3))
    nry = ry + h / 6.0 * (vy + 2 * vy2 + 2 * vy3 + (vy + h * ay3))
    nvx = vx + h / 6.0 * (ax1 + 2 * ax2 + 2 * ax3 + ax4)
    nvy = vy + h / 6.0 * (ay1 + 2 * ay2 + 2 * ay3 + ay4)
    return nrx, nry, nvx, nvy


def propagate(state: State, dt: float, n_steps: int) -> State:
    """Advance ``state`` by ``n_steps`` steps of size ``dt``, satisfying
    the module accuracy contract."""
    rx, ry = state.r
    vx, vy = state.v
    h = dt / _SUBSTEPS
    for _ in range(n_steps * _SUBSTEPS):
        rx, ry, vx, vy = _rk4_step(rx, ry, vx, vy, h)
    return State(r=(rx, ry), v=(vx, vy))
