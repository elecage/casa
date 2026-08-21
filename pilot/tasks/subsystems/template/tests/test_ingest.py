"""Checks that the input adapters run.

What is checked here is **shape** — that every source produces records, that
the status is one of the known values, that the timestamp parses. Whether the
values are right is not checked here. Values are compared against the
hand-counted expected values in `docs/reports/expected.md`.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from opsbox.ingest import ADAPTERS, read_all
from opsbox.record import Record, is_billable

DATA = Path(__file__).resolve().parents[1] / "data"


def test_every_registered_adapter_reads_something():
    records = read_all(DATA)
    seen = {r.source for r in records}
    assert seen == set(ADAPTERS), f"sources that read nothing: {set(ADAPTERS) - seen}"


def test_records_carry_the_shape_the_rest_of_the_tool_expects():
    for record in read_all(DATA):
        assert isinstance(record, Record)
        assert isinstance(record.at, datetime)
        assert isinstance(record.units, int)
        assert record.status in {"ok", "adjusted", "void"}
        assert record.account.strip() == record.account


def test_void_records_are_the_only_ones_left_out():
    records = read_all(DATA)
    assert [r for r in records if not is_billable(r)]
    for record in records:
        assert is_billable(record) is (record.status != "void")
