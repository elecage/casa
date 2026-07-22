"""Row parsing.

Timestamps may arrive naive (already UTC) or with an explicit UTC offset
(e.g. ``2025-03-01T19:05:00+09:00``). Either way, records leave this module
as naive UTC datetimes — see models.LogRecord.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .models import LogRecord


def _parse_ts(value: str) -> datetime:
    ts = datetime.fromisoformat(value)
    # Normalize to naive UTC so downstream comparisons are uniform.
    if ts.tzinfo is not None:
        ts = ts.astimezone(timezone.utc)
    return ts.replace(tzinfo=None)


def parse_row(row: dict[str, str]) -> LogRecord:
    return LogRecord(
        ts=_parse_ts(row["timestamp"]),
        path=row["path"],
        status=int(row["status"]),
        bytes_sent=int(row["bytes"]),
    )


def parse_rows(rows: list[dict[str, str]]) -> list[LogRecord]:
    return [parse_row(r) for r in rows]
