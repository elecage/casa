"""Produces the difference between the published number and the current one.
The spec is `docs/backfill.md`.

**Account names and the month boundary are worked out separately here.** The
account name rule already lives in the input adapters (subsystem A) and the
month boundary already lives in the aggregation (subsystem B), and this uses
neither but keeps rules of its own. When the rules diverge, the difference
does not line up with the report.
"""

from __future__ import annotations

import json
from pathlib import Path

from .._internal.timeparse import to_utc
from ..record import is_billable


def _account(raw: str) -> str:
    """The account name used in the backfill listing."""
    return raw.strip().lower()


def _month_of(record) -> str:
    """Which month this record belongs to. Keeps the zone offset and shifts to
    UTC."""
    when = to_utc(record.at_raw) if record.at_raw else record.at
    return f"{when.year:04d}-{when.month:02d}"


def published(root: Path, month: str) -> dict | None:
    path = Path(root) / "published" / f"{month}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def recomputed(records, month: str) -> dict:
    """That month's number, recounted from the current samples."""
    total = 0
    per_account: dict[str, int] = {}
    for record in records:
        if not is_billable(record) or _month_of(record) != month:
            continue
        total += record.units
        key = _account(record.account)
        per_account[key] = per_account.get(key, 0) + record.units
    return {"total_units": total, "by_account": dict(sorted(per_account.items()))}


def delta(root: Path, records, month: str) -> dict | None:
    """How much it moved from the published number."""
    before = published(root, month)
    if before is None:
        return None
    now = recomputed(records, month)
    return {
        "month": month,
        "published_total": before["total_units"],
        "recomputed_total": now["total_units"],
        "delta": now["total_units"] - before["total_units"],
        "by_account": now["by_account"],
    }
