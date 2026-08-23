"""Checks whether a threshold was crossed. The spec is `docs/alerts.md`.

**The month boundary is worked out separately here.** The aggregation
(subsystem B) makes the same judgement, and the two currently disagree — B
reads `MONTH_BASIS` in `opsbox/report/months.py`, while this one always shifts
to UTC. For records sitting on a month boundary the two sides' numbers come
apart.
"""

from __future__ import annotations

from .._internal.timeparse import to_utc
from ..record import is_billable


def _month_of(record) -> str:
    """Which month this record belongs to.

    Keeps the zone offset and shifts to UTC.
    """
    when = to_utc(record.at_raw) if record.at_raw else record.at
    return f"{when.year:04d}-{when.month:02d}"


def monthly_totals(records) -> dict[tuple[str, str], int]:
    """(account, month) -> units total."""
    out: dict[tuple[str, str], int] = {}
    for record in records:
        if not is_billable(record):
            continue
        key = (record.account, _month_of(record))
        out[key] = out.get(key, 0) + record.units
    return out


def last_seen(records) -> dict[str, int]:
    """The units on each account's most recent record."""
    latest: dict[str, tuple] = {}
    for record in records:
        if not is_billable(record):
            continue
        if record.account not in latest or record.at > latest[record.account][0]:
            latest[record.account] = (record.at, record.units)
    return {name: units for name, (_when, units) in latest.items()}


def fire(records, rules) -> list[dict]:
    """One alert per rule whose threshold was crossed."""
    totals = monthly_totals(records)
    latest = last_seen(records)
    out = []
    for rule in rules:
        account, limit = rule["account"], rule["limit"]
        basis = rule.get("basis", "month")
        if basis == "month":
            for (name, month), value in sorted(totals.items()):
                if name == account and value > limit:
                    out.append({"account": account, "month": month,
                                "basis": basis, "value": value, "limit": limit})
        elif basis == "last":
            value = latest.get(account)
            if value is not None and value > limit:
                out.append({"account": account, "month": None,
                            "basis": basis, "value": value, "limit": limit})
    return out
