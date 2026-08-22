"""Checks that aggregation and the report run.

What is checked here is **shape** — that the sections come out in order, that
no group is empty, that the total does not disagree with the sum of its parts.
**Whether the values are right is not checked here.** Values are compared
against the hand-counted expected values in `docs/reports/expected.md`.

**The date format and the month boundary are not pinned here either.** Those
are there to be decided; they are not a contract. Pinning them would make it
false that either choice is acceptable.
"""

from __future__ import annotations

from pathlib import Path

from opsbox.ingest import read_all
from opsbox.report import build, render_text

DATA = Path(__file__).resolve().parents[1] / "data"


def _report():
    return build(read_all(DATA))


def test_the_sections_the_report_already_has_come_out_in_order():
    """Sections the report may gain later are not pinned here."""
    text = render_text(_report())
    spots = [text.index(name) for name in
             ("## Totals", "## By source", "## By account", "## By month")]
    assert spots == sorted(spots)


def test_every_group_has_something_in_it():
    report = _report()
    for name in ("by_source", "by_account", "by_month"):
        assert report[name], f"{name} is empty"


def test_the_total_is_the_sum_of_the_parts():
    report = _report()
    assert sum(report["by_source"].values()) == report["total_units"]
    assert sum(report["by_account"].values()) == report["total_units"]
    assert sum(report["by_month"].values()) == report["total_units"]


def test_void_records_are_left_out_of_the_count():
    records = read_all(DATA)
    voided = [r for r in records if r.status == "void"]
    assert voided, "this check is meaningless if the sample has no void records"
    assert build(records)["record_count"] == len(records) - len(voided)


def test_months_are_written_as_year_and_month():
    for key in _report()["by_month"]:
        year, _, month = key.partition("-")
        assert len(year) == 4 and len(month) == 2
        assert year.isdigit() and month.isdigit()
