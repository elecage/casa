from datetime import datetime

from usagectl.record import Record
from usagectl.reports import percent


def rec(account, units):
    return Record(source="t", account=account, at=datetime(2026, 7, 1), units=units)


def test_shares_sum_to_about_one_hundred():
    rows = percent.render([rec("a", 1), rec("b", 1)])
    assert [r[1] for r in rows] == ["50.0", "50.0"]


def test_half_is_rounded_up():
    # 12.25% -> 12.3
    rows = percent.render([rec("a", 49), rec("b", 151)])
    assert rows[0][1] == "24.5"
