"""Checks that export runs.

**Shape only.** That the same input has to produce the same bytes is what
`docs/export.md` requires, and it does not hold right now. Pinning it here
would remove the thing that is there to be decided, so it is not checked here.
"""

from __future__ import annotations

from pathlib import Path

from opsbox.export import COLUMNS, to_csv
from opsbox.ingest import read_all
from opsbox.report import build

ROOT = Path(__file__).resolve().parents[1]


def _report():
    return build(read_all(ROOT / "data"))


def test_the_flat_export_carries_the_column_names_in_order():
    text = to_csv(_report())
    header = [line for line in text.splitlines() if not line.startswith("#")][0]
    assert header.split(",") == list(COLUMNS)


def test_every_account_in_the_report_comes_out():
    report = _report()
    text = to_csv(report)
    for account in report["by_account"]:
        assert account in text
