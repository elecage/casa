from datetime import datetime

from usagectl import reports
from usagectl.record import Record


def rec(source, account, units, day=1):
    return Record(source=source, account=account,
                  at=datetime(2026, 7, day), units=units)


def test_every_section_has_a_title_and_render():
    for module in reports.SECTIONS.values():
        assert isinstance(module.TITLE, str)
        assert callable(module.render)


def test_sources_groups_by_source():
    rows = reports.SECTIONS["sources"].render([rec("a", "x", 3), rec("b", "y", 4)])
    assert rows == [["a", "3"], ["b", "4"]]


def test_daily_groups_by_date():
    rows = reports.SECTIONS["daily"].render([rec("a", "x", 3, day=2),
                                             rec("a", "y", 4, day=2)])
    assert rows == [["2026-07-02", "7"]]
