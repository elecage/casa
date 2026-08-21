"""집계와 리포트가 도는지 본다.

여기서 보는 것은 **모양**이다 — 절이 순서대로 나오는지, 묶음이 비지 않는지,
합계가 부분의 합과 어긋나지 않는지. **값이 맞는지는 여기서 안 본다.**
값은 `docs/reports/expected.md`의 손으로 센 기대값과 견준다.

**날짜 표기와 달 경계도 여기서 고정하지 않는다.** 그것은 정할 자리이지
계약이 아니다. 고정해 버리면 어느 쪽을 골라도 된다는 말이 거짓이 된다.
"""

from __future__ import annotations

from pathlib import Path

from opsbox.ingest import read_all
from opsbox.report import build, render_text

DATA = Path(__file__).resolve().parents[1] / "data"


def _report():
    return build(read_all(DATA))


def test_the_report_carries_the_four_sections_in_order():
    text = render_text(_report())
    spots = [text.index(name) for name in
             ("## 합계", "## 원천별", "## 계정별", "## 달별")]
    assert spots == sorted(spots)


def test_every_group_has_something_in_it():
    report = _report()
    for name in ("by_source", "by_account", "by_month"):
        assert report[name], f"{name} 가 비었다"


def test_the_total_is_the_sum_of_the_parts():
    report = _report()
    assert sum(report["by_source"].values()) == report["total_units"]
    assert sum(report["by_account"].values()) == report["total_units"]
    assert sum(report["by_month"].values()) == report["total_units"]


def test_void_records_are_left_out_of_the_count():
    records = read_all(DATA)
    voided = [r for r in records if r.status == "void"]
    assert voided, "표본에 void 기록이 없으면 이 검사는 의미가 없다"
    assert build(records)["record_count"] == len(records) - len(voided)


def test_months_are_written_as_year_and_month():
    for key in _report()["by_month"]:
        year, _, month = key.partition("-")
        assert len(year) == 4 and len(month) == 2
        assert year.isdigit() and month.isdigit()
