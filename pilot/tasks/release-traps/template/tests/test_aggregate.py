from datetime import datetime

from usagectl.aggregate import by_account, by_month, grand_total
from usagectl.record import Record, is_billable


def rec(account, units, status="ok", day=1):
    return Record(source="t", account=account, at=datetime(2026, 7, day),
                  units=units, status=status)


def test_void_records_are_excluded():
    assert not is_billable(rec("a", 10, "void"))


def test_adjusted_records_are_counted():
    assert is_billable(rec("a", 10, "adjusted"))


def test_by_account_sums_and_sorts():
    assert by_account([rec("b", 5), rec("a", 3), rec("a", 2)]) == {"a": 5, "b": 5}


def test_by_month_groups_by_year_month():
    assert by_month([rec("a", 4, day=2), rec("a", 6, day=20)]) == {"2026-07": 10}


def test_grand_total_skips_void():
    assert grand_total([rec("a", 10), rec("b", 5, "void")]) == 10
