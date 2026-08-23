"""Release gate. See RELEASE.md for which cases are promises and which
describe the current implementation.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from meterhouse import rollup                      # noqa: E402
from meterhouse.intake import csvfeed              # noqa: E402
from meterhouse.record import Reading              # noqa: E402

DATA = ROOT / "data"


def test_units_are_normalized_to_kwh():
    readings, _ = csvfeed.read_file(DATA / "site-a-2026-07.csv")
    by_account = {r.account: r for r in readings if r.account == "ACC-1002"}
    # 318000 Wh is 318 kWh.
    assert any(r.quantity == Decimal("318") for r in readings)
    assert all(r.unit == "kWh" for r in readings)
    assert by_account


def test_skipped_rows_are_reported():
    _, skipped = csvfeed.read_file(DATA / "site-a-2026-07.csv")
    reasons = " ".join(skipped)
    assert "bad quantity" in reasons
    assert "unknown unit" in reasons


def test_reading_fields():
    reading = Reading(id="a01", account="ACC-1001",
                      observed_at="2026-07-02T00:00:00Z",
                      recorded_at="2026-07-02T06:00:00Z",
                      quantity=Decimal("1"), unit="kWh", corrects=None,
                      source_file="site-a-2026-07.csv", source_line=2)
    assert reading.as_dict() == {
        "id": "a01", "account": "ACC-1001",
        "observed_at": "2026-07-02T00:00:00Z",
        "recorded_at": "2026-07-02T06:00:00Z",
        "quantity": "1", "unit": "kWh", "corrects": None,
        "source": {"file": "site-a-2026-07.csv", "line": 2}}


def test_month_is_taken_from_the_observation():
    assert rollup.month_of("2026-07-31T23:00:00Z") == "2026-07"


def test_totals_add_up_per_account():
    readings, _ = csvfeed.read_file(DATA / "site-a-2026-07.csv")
    totals = rollup.totals(readings, "2026-07")
    assert totals["ACC-1001"] == Decimal("253.5")
