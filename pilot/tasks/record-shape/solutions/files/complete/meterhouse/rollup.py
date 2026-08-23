"""Monthly totals per account."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from .corrections import resolve
from .record import Reading


def month_of(at: str) -> str:
    return at[:7]


def totals(readings: list[Reading], month: str,
           as_of: str | None = None) -> dict[str, Decimal]:
    effective, _ = resolve(readings, as_of)
    out: dict[str, Decimal] = defaultdict(Decimal)
    for reading in effective:
        if month_of(reading.observed_at) == month:
            out[reading.account] += reading.quantity
    return dict(out)
