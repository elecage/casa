"""Grading-only enforcement of the split_with_fee cross-cutting contract.

Never shipped to sessions: the runner copies template/ only. These checks
attack the invariants that span the ledger's layers — integer minor-unit
discipline, remainder conservation, the single rounding rule, and the
validation gate — none of which the visible suite exercises.

Invariants are checked structurally (order of shares is not constrained),
so any correct implementation passes regardless of arrangement.
"""

import pytest

from ledger.api import process_split
from ledger.domain import split_with_fee
from ledger.money import Money
from ledger.validation import ValidationError


def _ref_round_half_even(numerator: int, denominator: int) -> int:
    q, r = divmod(numerator, denominator)
    twice = 2 * r
    if twice > denominator or (twice == denominator and q % 2 == 1):
        q += 1
    return q


def _check_types(result, currency="USD"):
    for m in list(result.net) + list(result.fee) + [result.total_fee]:
        assert isinstance(m, Money), f"expected Money, got {type(m)}"
        assert isinstance(m.minor, int) and not isinstance(m.minor, bool), (
            f"minor units must be int, got {m.minor!r}")
        assert m.currency == currency


def _check_contract(total: Money, n: int, rate_bps: int):
    result = split_with_fee(total, n, rate_bps)
    _check_types(result, total.currency)
    assert len(result.net) == n and len(result.fee) == n

    gross = [result.net[i].minor + result.fee[i].minor for i in range(n)]
    base = total.minor // n
    rem = total.minor - base * n

    # remainder conservation: gross shares sum to the principal and each is
    # base or base+1, with exactly `rem` of them bumped.
    assert sum(gross) == total.minor, f"principal not conserved: {gross}"
    assert all(g in (base, base + 1) for g in gross), f"uneven shares: {gross}"
    assert sum(1 for g in gross if g == base + 1) == rem

    # single rounding rule: each fee matches the system's banker's rounding.
    for i in range(n):
        expected = _ref_round_half_even(gross[i] * rate_bps, 10000)
        assert result.fee[i].minor == expected, (
            f"fee {result.fee[i].minor} != {expected} for gross {gross[i]}")
        assert result.net[i].minor == gross[i] - expected

    # value conservation across the whole operation.
    assert (sum(m.minor for m in result.net)
            + sum(m.minor for m in result.fee)) == total.minor
    assert result.total_fee.minor == sum(m.minor for m in result.fee)


def test_remainder_is_conserved():
    _check_contract(Money(10000), 3, 0)      # 100.00 / 3 -> 3334,3333,3333


def test_remainder_with_fee():
    _check_contract(Money(10000), 3, 250)    # remainder AND rounded fees


def test_half_even_rounding_point():
    # 2.5% of 5.00 = 0.125 -> banker's rounding -> 0.12 (even), not 0.13.
    _check_contract(Money(500), 1, 250)
    result = split_with_fee(Money(500), 1, 250)
    assert result.fee[0].minor == 12


def test_large_prime_split():
    _check_contract(Money(1000003), 7, 137)  # awkward remainder + rounding


def test_api_path_matches():
    a = split_with_fee(Money(10000), 3, 250)
    b = process_split(Money(10000), 3, 250)
    assert a.net == b.net and a.fee == b.fee


def test_no_float_leak():
    result = split_with_fee(Money(10000), 3, 250)
    for m in list(result.net) + list(result.fee):
        assert type(m.minor) is int


def test_validation_gate():
    # A Money amount and the rate flow through validation.py, which raises
    # ValidationError; the count n has no gate function in the module, so
    # any ValueError (ValidationError is one) counts as rejecting it.
    with pytest.raises(ValidationError):
        split_with_fee(Money(-100), 3, 250)     # negative principal
    with pytest.raises(ValueError):
        split_with_fee(Money(10000), 0, 250)    # non-positive n
    with pytest.raises(ValidationError):
        split_with_fee(Money(10000), 3, 20000)  # rate out of range
