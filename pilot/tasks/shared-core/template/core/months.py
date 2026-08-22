"""Where the month boundary goes. The spec is the "Month boundary" section of
`docs/report.md`.

**Once this is settled the alert rules (subsystem C) have to use the same
basis.** C puts thresholds on top of this aggregation, and with a different
basis the records sitting on a month boundary quietly produce a different
number. The tests stay green and nothing raises an error.
"""

from __future__ import annotations

from .timeparse import to_utc
from .record import Record

#: What the month boundary is taken to be: "local" or "utc".
#: Right now it is the local time exactly as the source wrote it. Which way to
#: go is decided by reading `docs/report.md`.
MONTH_BASIS = "local"


def moment(record: Record):
    """Which timestamp this record is viewed at."""
    if MONTH_BASIS == "utc" and record.at_raw:
        return to_utc(record.at_raw)
    return record.at


def month_key(record: Record) -> str:
    """`2026-07` form."""
    when = moment(record)
    return f"{when.year:04d}-{when.month:02d}"
