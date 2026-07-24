"""Bundled tests for quadroots.roots — a few well-conditioned cases only.
The full precision contract is in quadroots/roots.py."""

import math

from quadroots.roots import roots


def _close(got, expected):
    return all(math.isclose(g, e, rel_tol=1e-9, abs_tol=1e-9)
               for g, e in zip(got, expected))


def test_distinct_integer_roots():
    assert _close(roots(1, -3, 2), (1.0, 2.0))


def test_symmetric_roots():
    assert _close(roots(1, 0, -1), (-1.0, 1.0))


def test_repeated_root():
    assert _close(roots(1, -2, 1), (1.0, 1.0))


def test_negative_roots():
    assert _close(roots(1, 5, 6), (-3.0, -2.0))
