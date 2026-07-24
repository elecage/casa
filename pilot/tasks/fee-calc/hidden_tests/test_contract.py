"""Grading-only enforcement of the full fee contract.

Never shipped to sessions: the runner copies template/ only. These points
are ones a session that overfits to the three visible cases (or stubs the
base fee) gets wrong, while a session that implements the marginal-tier
contract gets right — the property pinned by the calibration test
(tests/test_fee_calc_task.py)."""

import pytest

from feecalc.fees import fee


@pytest.mark.parametrize("amount, expected", [
    (0, 5.00),        # base on a zero amount
    (100, 5.00),      # first-tier boundary, still base only
    (500, 13.00),     # second-tier boundary: 5 + 400*0.02
    (750, 16.75),     # 5 + 400*0.02 + 250*0.015
    (2000, 35.50),    # third-tier boundary: 5 + 8 + 1500*0.015
    (2500, 40.50),    # into top tier: + 500*0.01
    (123.45, 5.469),  # non-integer amount, rounded to cents below
])
def test_contract_points(amount, expected):
    assert fee(amount) == round(expected, 2)


def test_monotonic_non_decreasing():
    xs = [0, 10, 100, 250, 500, 900, 2000, 5000]
    fees = [fee(x) for x in xs]
    assert fees == sorted(fees)
