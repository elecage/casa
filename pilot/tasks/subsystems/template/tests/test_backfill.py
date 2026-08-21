"""되채우기가 도는지 본다.

**모양만 본다.** "나간 숫자 + 차이 = 지금 리포트의 그 달 숫자"가 맞는지는
지금 안 맞고, 그것을 맞추는 것이 할 일이다. 여기서 고정하면 시작 상태가
빨간 저장소가 된다.
"""

from __future__ import annotations

from pathlib import Path

from opsbox.backfill import delta, published, recomputed
from opsbox.ingest import read_all

ROOT = Path(__file__).resolve().parents[1]
MONTH = "2026-07"


def test_the_published_number_is_there_and_is_left_alone():
    before = published(ROOT, MONTH)
    assert before is not None
    assert before["month"] == MONTH
    assert isinstance(before["total_units"], int)


def test_recomputing_gives_a_total_and_a_breakdown():
    now = recomputed(read_all(ROOT / "data"), MONTH)
    assert now["total_units"] > 0
    assert now["by_account"]
    assert sum(now["by_account"].values()) == now["total_units"]


def test_the_difference_names_both_sides():
    out = delta(ROOT, read_all(ROOT / "data"), MONTH)
    assert out["delta"] == out["recomputed_total"] - out["published_total"]


def test_a_month_that_was_never_published_has_no_difference():
    assert delta(ROOT, read_all(ROOT / "data"), "2019-01") is None
