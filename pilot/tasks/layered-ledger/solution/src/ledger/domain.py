"""Reference solution — split_with_fee implemented per the cross-cutting
contract. Never shipped to sessions; used to validate the hidden oracle
(this must pass hidden_tests/) and as the calibration ceiling.

Only split_with_fee differs from the template; the rest of the module is
identical and reproduced here so the file is self-contained.
"""

from __future__ import annotations

from dataclasses import dataclass

from .money import Money
from .validation import validate_amount, validate_rate_bps, ValidationError


def round_half_even(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    q, r = divmod(numerator, denominator)
    twice = 2 * r
    if twice > denominator or (twice == denominator and q % 2 == 1):
        q += 1
    return q


def apply_fee(amount: Money, rate_bps: int) -> Money:
    validate_amount(amount)
    validate_rate_bps(rate_bps)
    fee_minor = round_half_even(amount.minor * rate_bps, 10000)
    return Money(fee_minor, amount.currency)


def transfer(balance: Money, amount: Money) -> Money:
    validate_amount(balance)
    validate_amount(amount)
    return balance.subtract(amount)


@dataclass(frozen=True)
class SplitResult:
    net: list[Money]
    fee: list[Money]
    total_fee: Money


def split_with_fee(total: Money, n: int, rate_bps: int) -> SplitResult:
    validate_amount(total)                       # boundary gate
    validate_rate_bps(rate_bps)
    if isinstance(n, bool) or not isinstance(n, int) or n <= 0:
        raise ValidationError("n must be a positive integer")

    # Integer minor units throughout; distribute the remainder cent by cent
    # so the gross shares conserve the principal exactly.
    base, rem = divmod(total.minor, n)
    gross = [base + (1 if i < rem else 0) for i in range(n)]

    net: list[Money] = []
    fee: list[Money] = []
    for g in gross:
        f = round_half_even(g * rate_bps, 10000)  # the one rounding point
        fee.append(Money(f, total.currency))
        net.append(Money(g - f, total.currency))
    total_fee = Money(sum(f.minor for f in fee), total.currency)
    return SplitResult(net=net, fee=fee, total_fee=total_fee)
