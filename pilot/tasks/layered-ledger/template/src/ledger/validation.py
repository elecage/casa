"""Input validation — the boundary gate.

Invariant (holds everywhere): every amount that enters a domain operation
from the outside is checked here first. Domain code does not re-check; it
trusts that values arrived through validation. Skipping this gate lets
negative or cross-currency amounts reach the ledger.
"""

from __future__ import annotations

from .money import Money


class ValidationError(ValueError):
    """Raised when an amount or operation parameter is not admissible."""


def validate_amount(amount: Money, *, allow_zero: bool = True) -> None:
    if not isinstance(amount, Money):
        raise ValidationError("amount must be a Money value")
    if amount.minor < 0:
        raise ValidationError("amount must be non-negative")
    if not allow_zero and amount.minor == 0:
        raise ValidationError("amount must be positive")


def validate_rate_bps(rate_bps: int) -> None:
    """A rate in basis points (1 bps = 0.01%). Must be an integer in
    [0, 10000] — fractional basis points are not representable."""
    if isinstance(rate_bps, bool) or not isinstance(rate_bps, int):
        raise ValidationError("rate_bps must be an integer")
    if not 0 <= rate_bps <= 10000:
        raise ValidationError("rate_bps must be within [0, 10000]")
