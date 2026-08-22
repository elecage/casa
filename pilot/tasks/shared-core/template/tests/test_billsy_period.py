"""What billing takes a billing period to be.

Written before the two products were put on one core. `RELEASE.md` says this
is the one test under `tests/` that may change when the boundary is settled.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from billsy import invoice  # noqa: E402
from core.record import Record  # noqa: E402
from core.timeparse import parse_ts  # noqa: E402


def _record(raw: str, units: int = 10, account: str = "acme-01") -> Record:
    return Record(source="ac", account=account, at=parse_ts(raw), units=units,
                  at_raw=raw)


def test_a_record_lands_in_the_period_its_local_time_says():
    assert invoice._period_of(_record("2026-07-31T23:30:00+09:00")) == "2026-07"


def test_a_plain_timestamp_lands_where_it_reads():
    assert invoice._period_of(_record("2026-08-01T00:10:00")) == "2026-08"
