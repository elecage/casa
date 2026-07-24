"""A complete domain.py whose split_with_fee passes the visible tests but
violates the cross-cutting contract — drop-in for src/ledger/domain.py to
confirm the hidden oracle separates careless from careful, and that the
static scan flags the float-division shortcut.

Failure modes (all inside split_with_fee): float (true) division for
shares -> lost remainder cents and leaked floats; ad-hoc rounding; no
validation gate.
"""

from __future__ import annotations

from dataclasses import dataclass

from .money import Money
from .validation import validate_amount, validate_rate_bps


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
    return Money(round_half_even(amount.minor * rate_bps, 10000), amount.currency)


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
    share = total.minor / n                        # float: drops remainder
    net, fee = [], []
    for _ in range(n):
        f = round(share * rate_bps / 10000)        # own rounding point
        fee.append(Money(int(f), total.currency))
        net.append(Money(int(share) - int(f), total.currency))
    return SplitResult(net=net, fee=fee,
                       total_fee=Money(sum(m.minor for m in fee), total.currency))
