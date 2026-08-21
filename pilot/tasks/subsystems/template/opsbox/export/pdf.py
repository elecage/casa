"""Produces one page of the report as a PDF. The shape is in
`docs/export.md`."""

from __future__ import annotations

from pathlib import Path


def write(path, report: dict, title: str = "opsbox usage") -> None:
    from vendor.minipdf import write_table

    rows = [("Records", report["record_count"]),
            ("Units total", report["total_units"])]
    rows += [(f"Source {name}", value)
             for name, value in report["by_source"].items()]
    write_table(Path(path), title, rows)
