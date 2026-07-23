"""Record validation shared by every exporter.

A record is a dict with the fields in FIELD_ORDER. Exporters emit fields
in exactly that order, regardless of dict insertion order.
"""

from __future__ import annotations

from .errors import ExportError

FIELD_ORDER = ("id", "name", "value")
REQUIRED_FIELDS = frozenset(FIELD_ORDER)


def check_records(records: list[dict]) -> None:
    if not records:
        raise ExportError("nothing to export")
    for i, rec in enumerate(records):
        if not isinstance(rec, dict):
            raise ExportError(f"record {i} is not a mapping")
        missing = REQUIRED_FIELDS - rec.keys()
        if missing:
            raise ExportError(f"record {i} missing fields: {sorted(missing)}")
