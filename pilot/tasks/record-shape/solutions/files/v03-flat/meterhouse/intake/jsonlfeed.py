"""JSONL feed adapter.

The newer sites push one JSON object per line. Same fields as the CSV feed;
see `docs/v03-metering.md`.
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from ..record import Reading
from .csvfeed import normalize_unit, to_kwh


def read_file(path: Path) -> tuple[list[Reading], list[str]]:
    """Return (readings, skipped) for one JSONL file."""
    path = Path(path)
    readings: list[Reading] = []
    skipped: list[str] = []
    with open(path, encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                skipped.append(f"{path.name}:{line_no}: bad quantity")
                continue
            unit = normalize_unit(str(row.get("unit") or ""))
            if unit is None:
                skipped.append(f"{path.name}:{line_no}: unknown unit")
                continue
            try:
                quantity = Decimal(str(row.get("quantity") or "").strip())
            except InvalidOperation:
                skipped.append(f"{path.name}:{line_no}: bad quantity")
                continue
            readings.append(Reading(
                account=str(row.get("account") or ""),
                at=str(row.get("observed_at") or ""),
                quantity=to_kwh(quantity, unit),
                unit="kWh",
            ))
    return readings, skipped
