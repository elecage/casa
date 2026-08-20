"""릴리스 항목별 호출 귀속 테스트 (`pilot/tasks/release-traps/attribute.py`).

세 가지를 못 박는다.

1. **겹치는 경로는 더 좁은 쪽이 이긴다.** 합계 어긋남의 원인 파일은
   `usagectl/readers/` 아래 있지만 1번이 아니라 5번 항목의 일이다.
2. **걸치거나 어디에도 안 드는 호출은 미귀속이다.** 지어내지 않는다.
3. **비율은 귀속된 호출만으로 잰다.** 미귀속을 분모에 넣으면 항목 경계 밖에서
   헤맨 세션이 오히려 쏠림이 낮게 나온다.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TASK = Path(__file__).resolve().parents[1] / "pilot" / "tasks" / "release-traps"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


attribute = _load("release_traps_attribute_test", TASK / "attribute.py")


# ------------------------------------------------------------- 경로 하나

def test_the_narrower_path_wins():
    """원인 파일은 readers/ 아래 있지만 5번 항목의 일이다."""
    assert attribute.item_for("usagectl/readers/sjl.py") == "mismatch"
    assert attribute.item_for("usagectl/readers/sth.py") == "sources"
    assert attribute.item_for("usagectl/aggregate.py") == "mismatch"


def test_documents_split_by_what_they_document():
    assert attribute.item_for("docs/spec.md") == "json"
    assert attribute.item_for("docs/reports/summary.md") == "summary"
    assert attribute.item_for("docs/readers/stp.md") == "docs"
    assert attribute.item_for("docs/limits.md") == "docs"


def test_a_pdf_belongs_to_the_pdf_item_wherever_it_lands():
    """산출물이 어디에 놓일지는 우리가 못 정한다."""
    assert attribute.item_for("report.pdf") == "pdf"
    assert attribute.item_for("usagectl/reports/pdf_out.py") == "pdf"
    assert attribute.item_for("vendor/minipdf.py") == "pdf"


def test_windows_paths_and_leading_dots_are_the_same_path():
    assert attribute.item_for("usagectl\\cli.py") == "json"
    assert attribute.item_for("./STATUS.md") == "status"


def test_procedure_files_belong_to_no_item():
    """버전 문자열과 변경 기록은 항목이 아니라 절차다."""
    for path in attribute.PROCEDURE_PATHS:
        assert attribute.item_for(path) is None, path


# ------------------------------------------------------------- 호출 하나

def test_a_call_inside_one_item_is_attributed():
    assert attribute.attribute_call(
        ["usagectl/readers/sth.py", "usagectl/readers/ssc.py"]) == "sources"


def test_a_call_across_two_items_is_left_unattributed():
    assert attribute.attribute_call(
        ["usagectl/cli.py", "STATUS.md"]) is None


def test_a_call_touching_nothing_of_ours_is_left_unattributed():
    assert attribute.attribute_call(["CHANGELOG.md"]) is None
    assert attribute.attribute_call([]) is None


def test_an_item_file_plus_a_procedure_file_still_counts_for_the_item():
    """절차 파일은 항목이 없으므로 걸침이 아니다."""
    assert attribute.attribute_call(
        ["usagectl/cli.py", "CHANGELOG.md"]) == "json"


# --------------------------------------------------------------- 도출

def test_the_window_is_the_median_calls_spent_on_one_item():
    sessions = [["json"] * 4 + ["docs"] * 20,
                ["json"] * 4 + ["docs"] * 20]
    # 항목별 호출 수는 [4, 20, 4, 20] → 중앙값 12
    assert attribute.window_from(sessions) == 12


def test_untouched_items_do_not_drag_the_window_down():
    """손도 안 댄 항목의 0을 넣으면 창이 항목 수에 따라 줄어든다."""
    sessions = [["json"] * 12]
    assert attribute.window_from(sessions) == 12


def test_the_share_only_counts_attributed_calls():
    """미귀속을 섞어도 비율이 묽어지지 않는다."""
    packed = [["docs"] * 10]
    diluted = [[None, "docs", None, "docs", None] * 2 + ["docs"] * 8]
    assert attribute.p90(attribute.shares(packed, 10)) == 1.0
    assert attribute.p90(attribute.shares(diluted, 10)) == 1.0


def test_a_scattered_session_shows_a_low_share():
    session = [["sources", "json", "summary", "pdf", "mismatch",
                "docs", "status", "sources", "json", "summary"]]
    assert attribute.p90(attribute.shares(session, 10)) == 0.2


def test_the_floor_is_used_when_the_data_says_less():
    """봉인된 규칙 — 도출된 값이 하한보다 낮으면 하한을 쓴다."""
    scattered = [["sources", "json", "summary", "pdf"]]
    out = attribute.derive(scattered)
    assert out["window_final"] == attribute.FLOORS["window"]
    assert out["share_final"] == attribute.FLOORS["share"]
    assert out["window_seen"] == 1


def test_derive_counts_what_it_could_not_attribute():
    out = attribute.derive([["json", None, "json"]])
    assert (out["attributed"], out["unattributed"]) == (2, 1)


# ------------------------------------------------- 달성 항목과 세션 분량

def test_items_true_at_the_start_do_not_count_as_progress():
    checks = {"tests.green": True, "json.matches_spec": True,
              "pdf.produced": False, "summary.matches_spec": None}
    assert attribute.newly_achieved(checks) == 1


def test_how_many_sessions_of_work_the_repository_holds():
    """세션 하나가 두 항목을 채우면 여덟 항목은 네 세션 분량이다."""
    assert attribute.sessions_worth_of_work([2, 2, 2], total_items=8) == 4.0


def test_no_session_finished_anything_means_no_estimate():
    assert attribute.sessions_worth_of_work([0, 0], total_items=8) is None
