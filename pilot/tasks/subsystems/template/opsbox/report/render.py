"""Writes the report out as text. The sections are in `docs/report.md`."""

from __future__ import annotations

from .dates import format_date


def render_text(report: dict, generated_at=None) -> str:
    lines = ["# opsbox usage report", ""]
    if generated_at is not None:
        lines += [f"Generated on: {format_date(generated_at)}", ""]
    lines += ["## Totals", "",
              f"{report['record_count']} records, {report['total_units']} units",
              "", "## By source", ""]
    for name, value in report["by_source"].items():
        lines.append(f"- {name}: {value}")
    lines += ["", "## By account", ""]
    for name, value in report["by_account"].items():
        lines.append(f"- {name}: {value}")
    lines += ["", "## By month", ""]
    for key, value in report["by_month"].items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines) + "\n"
