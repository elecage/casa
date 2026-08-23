"""Monthly totals per account."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from .record import Reading


def month_of(at: str) -> str:
    return at[:7]


def totals(readings: list[Reading], month: str) -> dict[str, Decimal]:
    out: dict[str, Decimal] = defaultdict(Decimal)
    for reading in readings:
        if month_of(reading.at) == month:
            out[reading.account] += reading.quantity
    return dict(out)
