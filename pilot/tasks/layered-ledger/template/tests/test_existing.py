"""Existing behavior — passes as shipped. Do not modify."""

import pytest

from ledger.domain import apply_fee, round_half_even, transfer
from ledger.money import Money
from ledger.repository import AccountRepository
from ledger.serialize import format_money, parse_money
from ledger.validation import ValidationError, validate_amount


def test_money_rejects_non_integer():
    with pytest.raises(TypeError):
        Money(1.5)
    with pytest.raises(TypeError):
        Money(True)


def test_apply_fee_rounds_once():
    assert apply_fee(Money(1000), 100) == Money(10)      # 1% of 10.00 = 0.10, exact
    # 2.5% of 5.00 = 0.125 -> half to even -> 0.12 (12 is even)
    assert apply_fee(Money(500), 250) == Money(12)
    assert round_half_even(12500, 10000) == 1            # 1.25 -> 1
    assert round_half_even(2500, 10000) == 0             # 0.25 -> 0


def test_transfer_debits():
    assert transfer(Money(10000), Money(2500)) == Money(7500)


def test_validation_rejects_negative():
    with pytest.raises(ValidationError):
        validate_amount(Money(-1))


def test_serialize_round_trip():
    m = Money(123456)
    assert format_money(m) == "1234.56 USD"
    assert parse_money(format_money(m)) == m


def test_repository_round_trip():
    repo = AccountRepository()
    repo.save("acct-1", Money(5000))
    assert repo.load("acct-1") == Money(5000)
