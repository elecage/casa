"""Checks that archiving and cleanup run.

**Shape only.** Whether to pick by age or by size, and how dates are written,
are there to be decided, so they are not pinned here.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from opsbox.archive import by_age, by_size, older_than, render
from opsbox.config import load
from opsbox.ingest import read_all

ROOT = Path(__file__).resolve().parents[1]


def _setup():
    config = load(ROOT)
    records = read_all(ROOT / "data")
    return records, config, datetime.fromisoformat(config["as_of"])


def test_the_age_filter_keeps_only_records_before_the_cutoff():
    records, config, as_of = _setup()
    picked = older_than(records, as_of, config["retain_days"])
    assert picked, "this check is meaningless if nothing is up for archiving"
    for record in picked:
        assert (as_of - record.at).days >= config["retain_days"]


def test_both_ways_of_picking_return_counts_per_account():
    records, config, as_of = _setup()
    for picked in (by_age(records, as_of, config["retain_days"]),
                   by_size(records, 100)):
        assert isinstance(picked, dict)
        for name, value in picked.items():
            assert isinstance(name, str) and name
            assert isinstance(value, int) and value > 0


def test_the_manifest_names_the_day_it_was_made_and_the_accounts():
    records, config, as_of = _setup()
    out = render(by_age(records, as_of, config["retain_days"]), as_of)
    assert out["as_of"]
    assert out["accounts"]
    for entry in out["accounts"]:
        assert set(entry) == {"account", "records"}
