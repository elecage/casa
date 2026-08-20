"""레코드를 계정별·월별로 집계한다."""

from __future__ import annotations

from collections import defaultdict

from .record import Record, is_billable


def by_account(records: list[Record]) -> dict[str, int]:
    totals: dict[str, int] = defaultdict(int)
    for record in records:
        if is_billable(record):
            totals[record.account] += record.units
    return dict(sorted(totals.items()))


def by_month(records: list[Record]) -> dict[str, int]:
    totals: dict[str, int] = defaultdict(int)
    for record in records:
        if is_billable(record):
            totals[record.at.strftime("%Y-%m")] += record.units
    return dict(sorted(totals.items()))


def grand_total(records: list[Record]) -> int:
    return sum(r.units for r in records if is_billable(r))
