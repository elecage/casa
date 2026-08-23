"""Subsystem B — aggregation and report. The spec is `docs/report.md`.

Takes the records the input adapters (subsystem A) hand back, groups them by
month, by source and by account, and produces a text report.

**Two things decided here carry into other subsystems.**

- **Month boundary** (`months.MONTH_BASIS`) — the alert rules (C) have to use
  the same basis.
- **Date format** (`dates.DATE_STYLE`) — the manifest from archiving and
  cleanup (D) has to use the same format.
"""

from __future__ import annotations

from . import accounts, dates, months, render, sources, totals
from .accounts import by_account
from .dates import format_date
from .months import month_key
from .render import render_text
from .sources import by_source
from .totals import record_count, total_units


def build(records) -> dict:
    """Collect everything that goes into the report in one lump."""
    per_month: dict[str, list] = {}
    for record in records:
        per_month.setdefault(month_key(record), []).append(record)
    return {
        "total_units": total_units(records),
        "record_count": record_count(records),
        "by_source": by_source(records),
        "by_account": by_account(records),
        "by_month": {key: total_units(rows)
                     for key, rows in sorted(per_month.items())},
    }
