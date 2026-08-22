"""Writes the archive manifest. The shape is in `docs/archive.md`."""

from __future__ import annotations

from datetime import datetime

from ..report.dates import format_date


def render(picked: dict[str, int], as_of: datetime) -> dict:
    """One archive manifest.

    Dates are written with `opsbox.report.dates.format_date` — built in one
    place so the repo does not end up with two date formats.
    """
    return {
        "as_of": format_date(as_of),
        "accounts": [{"account": name, "records": count}
                     for name, count in sorted(picked.items())],
    }
