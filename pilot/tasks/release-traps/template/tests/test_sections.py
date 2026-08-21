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
    """같은 날짜의 기록을 한 줄로 묶는다.

    **날짜를 어떤 표기로 적는지는 여기서 못 박지 않는다.** 표기는 문서가 정할
    일이고, 문서 두 곳이 지금 서로 다른 말을 하고 있다.
    """
    rows = reports.SECTIONS["daily"].render([rec("a", "x", 3, day=2),
                                             rec("a", "y", 4, day=2)])
    assert len(rows) == 1
    day, units = rows[0]
    assert units == "7"
    assert "2026" in day and "02" in day
