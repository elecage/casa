"""Totals. Only what is billable gets counted."""

from __future__ import annotations

from ..record import is_billable


def total_units(records) -> int:
    return sum(r.units for r in records if is_billable(r))


def record_count(records) -> int:
    return sum(1 for r in records if is_billable(r))
