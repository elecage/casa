"""Per-window aggregation."""

from __future__ import annotations

from .models import LogRecord, Window, WindowStats


def summarize(assigned: list[tuple[Window, list[LogRecord]]]) -> list[WindowStats]:
    stats = []
    for window, records in assigned:
        stats.append(WindowStats(
            start=window.start,
            end=window.end,
            count=len(records),
            errors=sum(1 for r in records if r.status >= 500),
            bytes_total=sum(r.bytes_sent for r in records),
        ))
    return stats
