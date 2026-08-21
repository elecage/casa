"""원천별 합계."""

from __future__ import annotations

from ..record import is_billable


def by_source(records) -> dict[str, int]:
    out: dict[str, int] = {}
    for record in records:
        if is_billable(record):
            out[record.source] = out.get(record.source, 0) + record.units
    return dict(sorted(out.items()))
