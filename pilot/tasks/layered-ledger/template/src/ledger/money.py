"""Money value object — the single representation of an amount in this
system.

Invariant (holds everywhere, enforced by this type): an amount is stored
as an **integer number of minor units** (cents), never as a float or a
decimal string. Formatting to a human-readable decimal happens only at the
serialization boundary (see serialize.py). Arithmetic stays in minor units.
"""

from __future__ import annotations


class Money:
    __slots__ = ("minor", "currency")

    def __init__(self, minor: int, currency: str = "USD") -> None:
        # bool is an int subclass; reject it so True/False cannot masquerade
        # as an amount, and reject floats so no fractional cent ever enters.
        if isinstance(minor, bool) or not isinstance(minor, int):
            raise TypeError("Money stores integer minor units (cents) only")
        self.minor = minor
        self.currency = currency

    def __eq__(self, other: object) -> bool:
        return (isinstance(other, Money)
                and self.minor == other.minor
                and self.currency == other.currency)

    def __hash__(self) -> int:
        return hash((self.minor, self.currency))

    def __repr__(self) -> str:
        return f"Money({self.minor}, {self.currency!r})"

    def _same_currency(self, other: "Money") -> None:
        if self.currency != other.currency:
            raise ValueError(
                f"currency mismatch: {self.currency} vs {other.currency}")

    def add(self, other: "Money") -> "Money":
        self._same_currency(other)
        return Money(self.minor + other.minor, self.currency)

    def subtract(self, other: "Money") -> "Money":
        self._same_currency(other)
        return Money(self.minor - other.minor, self.currency)
