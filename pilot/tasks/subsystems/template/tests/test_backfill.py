"""Checks that backfill runs.

**Shape only.** Whether "published number + difference = this month's number
in the current report" holds is exactly what does not hold right now, and
making it hold is the work. Pinning it here would make the starting state a
repo with failing tests.
"""

from __future__ import annotations

from pathlib import Path

from opsbox.backfill import delta, published, recomputed
from opsbox.ingest import read_all

ROOT = Path(__file__).resolve().parents[1]
MONTH = "2026-07"


def test_the_published_number_is_there_and_is_left_alone():
    before = published(ROOT, MONTH)
    assert before is not None
    assert before["month"] == MONTH
    assert isinstance(before["total_units"], int)


def test_recomputing_gives_a_total_and_a_breakdown():
    now = recomputed(read_all(ROOT / "data"), MONTH)
    assert now["total_units"] > 0
    assert now["by_account"]
    assert sum(now["by_account"].values()) == now["total_units"]


def test_the_difference_names_both_sides():
    out = delta(ROOT, read_all(ROOT / "data"), MONTH)
    assert out["delta"] == out["recomputed_total"] - out["published_total"]


def test_a_month_that_was_never_published_has_no_difference():
    assert delta(ROOT, read_all(ROOT / "data"), "2019-01") is None
