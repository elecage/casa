"""보관과 정리가 도는지 본다.

**모양만 본다.** 나이로 고를지 크기로 고를지, 날짜를 어떻게 적을지는
정할 자리이므로 여기서 고정하지 않는다.
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
    assert picked, "보관 대상이 하나도 없으면 이 검사는 의미가 없다"
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
