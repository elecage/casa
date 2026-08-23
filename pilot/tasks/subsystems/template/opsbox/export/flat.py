"""Exports the report as a flat table. The shape is in `docs/export.md`."""

from __future__ import annotations

import datetime

#: The order of the exported columns. Has to match `docs/export.md`.
COLUMNS = ("account", "month", "units")


def rows(report: dict) -> list[tuple]:
    out = []
    for account, units in sorted(report["by_account"].items()):
        out.append((account, "", units))
    return out


def to_csv(report: dict) -> str:
    """Comma separated table.

    The first line carries the time it was built, so you can tell when it was
    exported.
    """
    stamp = datetime.datetime.now().isoformat(timespec="seconds")
    lines = [f"# generated {stamp}", ",".join(COLUMNS)]
    for row in rows(report):
        lines.append(",".join(str(value) for value in row))
    return "\n".join(lines) + "\n"
