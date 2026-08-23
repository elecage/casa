"""CSV feed adapter.

The vendor writes one file per month per site. Columns are described in
`docs/v03-metering.md`.
"""

from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path

from ..record import Reading

UNITS = {"kwh": "kWh", "kWh": "kWh", "wh": "Wh", "Wh": "Wh"}


def normalize_unit(raw: str) -> str | None:
    return UNITS.get(raw.strip())


def to_kwh(quantity: Decimal, unit: str) -> Decimal:
    if unit == "Wh":
        return quantity / Decimal(1000)
    return quantity


def read_file(path: Path) -> tuple[list[Reading], list[str]]:
    """Return (readings, skipped) for one CSV file."""
    readings: list[Reading] = []
    skipped: list[str] = []
    with open(path, newline="", encoding="utf-8") as handle:
        for line_no, row in enumerate(csv.DictReader(handle), start=2):
            unit = normalize_unit(row.get("unit") or "")
            if unit is None:
                skipped.append(f"{path.name}:{line_no}: unknown unit")
                continue
            try:
                quantity = Decimal((row.get("quantity") or "").strip())
            except InvalidOperation:
                skipped.append(f"{path.name}:{line_no}: bad quantity")
                continue
            readings.append(Reading(
                account=(row.get("account") or "").strip(),
                at=(row.get("observed_at") or "").strip(),
                quantity=to_kwh(quantity, unit),
                unit="kWh",
            ))
    return readings, skipped
