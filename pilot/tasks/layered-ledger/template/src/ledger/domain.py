"""Domain operations on money — all arithmetic in integer minor units.

Invariant (holds everywhere): whenever a division would produce a
fractional cent, the result is rounded at exactly **one** place —
``round_half_even`` below — using banker's rounding (half to even). No
operation rounds a second time and none uses floating point. ``apply_fee``
is the worked example of the rule; new operations follow it.
"""

from __future__ import annotations

from dataclasses import dataclass

from .money import Money
from .validation import validate_amount, validate_rate_bps


def round_half_even(numerator: int, denominator: int) -> int:
    """Integer division rounding halves to the nearest even quotient.

    The single rounding point for the whole system. Both arguments are
    integers; the result is an integer number of minor units.
    """
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    q, r = divmod(numerator, denominator)
    twice = 2 * r
    if twice > denominator or (twice == denominator and q % 2 == 1):
        q += 1
    return q


def apply_fee(amount: Money, rate_bps: int) -> Money:
    """Return the fee charged on ``amount`` at ``rate_bps`` basis points,
    rounded once via :func:`round_half_even`. Worked example of the
    system's money-handling contract: validate, compute in minor units,
    round at the one point, return Money."""
    validate_amount(amount)
    validate_rate_bps(rate_bps)
    fee_minor = round_half_even(amount.minor * rate_bps, 10000)
    return Money(fee_minor, amount.currency)


def transfer(balance: Money, amount: Money) -> Money:
    """Debit ``amount`` from ``balance`` (both validated Money)."""
    validate_amount(balance)
    validate_amount(amount)
    return balance.subtract(amount)


@dataclass(frozen=True)
class SplitResult:
    """Outcome of :func:`split_with_fee`.

    ``net`` is what each recipient receives after fee, ``fee`` is the fee
    withheld from each, both as Money and index-aligned. ``total_fee`` is
    the sum of withheld fees.
    """
    net: list[Money]
    fee: list[Money]
    total_fee: Money


def split_with_fee(total: Money, n: int, rate_bps: int) -> SplitResult:
    """Split ``total`` among ``n`` recipients, withholding a fee at
    ``rate_bps`` basis points from each recipient's gross share.

    Contract:
    - Each recipient's gross share is ``total`` divided ``n`` ways. The
      division need not be exact; the split must still conserve every
      minor unit (the gross shares sum back to ``total``).
    - A fee at ``rate_bps`` is withheld from each gross share; each
      recipient receives net = gross - fee.
    - The whole operation conserves value: the sum of all net amounts plus
      all withheld fees equals ``total`` exactly.
    - Results are Money in ``total``'s currency.

    The bundled tests check only clean, evenly-divisible cases; grading
    enforces the full contract, including conservation over amounts that do
    not divide evenly and fees that require rounding.
    """
    raise NotImplementedError("split_with_fee is not implemented yet")
