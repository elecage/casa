"""Checks that the alert rules run.

**Shape only.** Which rules ought to fire is not pinned here — the month
boundary and the threshold basis are there to be decided. Pinning them would
make it false that either choice is acceptable.
"""

from __future__ import annotations

from pathlib import Path

from opsbox.alerts import fire, load, monthly_totals
from opsbox.ingest import read_all

ROOT = Path(__file__).resolve().parents[1]


def test_the_rules_file_is_readable_and_not_empty():
    rules = load(ROOT)
    assert rules
    for rule in rules:
        assert "account" in rule and "limit" in rule
        assert isinstance(rule["limit"], int)


def test_an_alert_names_what_it_compared():
    for alert in fire(read_all(ROOT / "data"), load(ROOT)):
        assert alert["value"] > alert["limit"]
        assert alert["account"]
        assert alert["basis"] in {"month", "last"}


def test_monthly_totals_cover_every_account_that_has_records():
    records = read_all(ROOT / "data")
    seen = {account for account, _month in monthly_totals(records)}
    billable = {r.account for r in records if r.status != "void"}
    assert seen == billable
