"""Bundled tests for feecalc.fee — these check only a few points of the
fee contract documented in feecalc/fees.py."""

from feecalc.fees import fee


def test_below_first_tier_is_base_only():
    assert fee(50) == 5.00


def test_into_second_tier():
    assert fee(300) == 9.00


def test_into_third_tier():
    assert fee(1000) == 20.50
