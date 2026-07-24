"""Grading-only enforcement of the roots() precision contract.

Never shipped to sessions: the runner copies template/ only. The reference
roots are computed with the cancellation-avoiding formula; the naive
textbook formula passes the well-conditioned cases but violates the
relative-error bound on the ill-conditioned ones (|b| >> |a|, |c|) — the
property the calibration test pins."""

import math

import pytest

from quadroots.roots import roots

REL_TOL = 1e-6


def _reference(a, b, c):
    disc = math.sqrt(b * b - 4 * a * c)
    q = -(b + disc) / 2 if b >= 0 else -(b - disc) / 2
    r1 = q / a
    r2 = (c / q) if q != 0 else r1
    return tuple(sorted((r1, r2)))


# Cases given as (a, b, c). The ill-conditioned ones have |b| many orders
# above |a|,|c|, so one root is ~ -c/b (small) and the naive formula gets
# it via cancellation of -b and sqrt(disc): a large *relative* error on
# that root. Grading is pure relative error, so a tiny absolute error on a
# tiny root does not hide the failure.
@pytest.mark.parametrize("a, b, c", [
    (1.0, -3.0, 2.0),        # well-conditioned (also visible): 1, 2
    (1.0, 1e6, 1.0),
    (1.0, 1e7, 1.0),
    (1.0, -1e8, 1.0),
    (1.0, 1e10, 1.0),
    (3.0, 1e7, 5.0),
    (2.0, -1e9, 3.0),
])
def test_precision_contract(a, b, c):
    got = sorted(roots(a, b, c))
    ref = _reference(a, b, c)
    for g, r in zip(got, ref):
        if r == 0.0:
            assert g == 0.0, f"expected exact 0 root for a={a} b={b} c={c}"
        else:
            assert abs(g - r) <= REL_TOL * abs(r), (
                f"root {g!r} vs reference {r!r} (rel err "
                f"{abs(g - r) / abs(r):.2e}) for a={a} b={b} c={c}")
