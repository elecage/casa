"""Visible checks for split_with_fee — clean, evenly-divisible cases only.

These fail until split_with_fee is implemented. They deliberately avoid
remainders, rounding, and invalid inputs; grading enforces those. Do not
modify.
"""

from ledger.api import process_split
from ledger.money import Money


def test_even_split_no_fee():
    result = process_split(Money(30000), 3, 0)      # 300.00 three ways
    assert result.net == [Money(10000), Money(10000), Money(10000)]
    assert result.total_fee == Money(0)


def test_even_split_with_exact_fee():
    result = process_split(Money(100000), 2, 100)   # 1000.00 two ways, 1%
    assert result.net == [Money(49500), Money(49500)]
    assert result.total_fee == Money(1000)
