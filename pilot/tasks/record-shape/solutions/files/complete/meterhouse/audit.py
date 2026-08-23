"""Audit trail (`docs/v05-audit.md`).

Shows the source rows behind one account's monthly total.
"""

from __future__ import annotations

from decimal import Decimal

from .corrections import known_at, superseded_by
from .record import Reading
from .rollup import month_of


def trail(readings: list[Reading], month: str, account: str,
          as_of: str | None = None) -> dict:
    visible = known_at(readings, as_of)
    superseded = superseded_by(visible)
    mine = [r for r in visible
            if r.account == account and month_of(r.observed_at) == month]
    quantity = Decimal(0)
    sources = []
    for reading in sorted(mine, key=lambda r: (r.source_file, r.source_line)):
        replaced = superseded.get(reading.id)
        if replaced is None:
            quantity += reading.quantity
        sources.append({"id": reading.id, "file": reading.source_file,
                        "line": reading.source_line,
                        "quantity": str(reading.quantity),
                        "superseded_by": replaced})
    return {"account": account, "month": month, "quantity": str(quantity),
            "as_of": as_of, "sources": sources}
