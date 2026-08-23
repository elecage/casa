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


# ------------------------------------------------- 분석 스크립트 끝에서 끝까지

def test_the_analysis_script_reads_real_snapshots(tmp_path):
    """스냅숏 저장소에서 호출별 변경을 꺼내 항목에 붙이는 데까지 돈다.

    이 프로젝트가 되풀이해 속은 자리가 전부 여기다 — 색인, 상대 경로,
    줄바꿈. 순수 함수만 시험하면 그 셋을 하나도 못 잡는다.
    """
    import json
    import subprocess

    analysis = _load("casa_call_attribution",
                     Path(__file__).resolve().parents[1] / "pilot" / "analysis"
                     / "call_attribution.py")
    snapshot = _load("casa_snapshot_for_attribution",
                     Path(__file__).resolve().parents[1] / "pilot" / "snapshot.py")

    out = tmp_path / "out"
    work = out / "work-01"
    (work / "usagectl" / "readers").mkdir(parents=True)
    (work / "usagectl" / "cli.py").write_text("x=1\n", encoding="utf-8")
    (work / "usagectl" / "readers" / "sjl.py").write_text("r\n", encoding="utf-8")
    (work / "CHANGELOG.md").write_text("c\n", encoding="utf-8")
    snapshot.install(work, out / "snapshots" / "work-01.git")

    for path, text in [("usagectl/cli.py", "x=2\n"),
                       ("usagectl/cli.py", "x=3\n"),
                       ("usagectl/readers/sjl.py", "r2\n"),
                       ("CHANGELOG.md", "c2\n")]:
        (work / path).write_text(text, encoding="utf-8")
        assert snapshot.take(work) is not None, path

    (out / "session-01.json").write_text(json.dumps({
        "session_index": 1,
        "grade": {"checkpoints": {"tests.green": True, "json.matches_spec": True,
                                  "pdf.produced": False}}}), encoding="utf-8")

    changes, dropped = analysis.session_changes(
        (out / "snapshots" / "work-01.git").resolve())
    assert dropped == 0                  # 시작 상태 커밋이 있으니 잃는 호출이 없다
    marks = attribute.attribute_session(changes)
    assert marks == ["json", "json", "mismatch", None]

    done = subprocess.run([sys.executable, str(analysis.__file__), str(out)],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace")
    assert done.returncode == 0, done.stderr
    assert "세션 점수가 아니다" in done.stdout      # 결과 채점으로 읽히면 안 된다


# ------------- 2026-08-21에 늘린 다섯 항목 (배치가 끝난 뒤에 넣었다)

def test_every_item_the_handoff_table_knows_has_a_place_in_the_path_table():
    """인계 판정이 아는 항목 이름은 경로 표에도 있어야 한다.

    없으면 그 항목의 일을 한 호출이 옛 항목 이름으로 찍히고, "손도 안 댐"과
    "손댔지만 못 고침"이 뒤바뀐다.
    """
    import importlib.util
    import sys
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "pilot" / "analysis" / "chain_eval.py"
    spec = importlib.util.spec_from_file_location("attr_chain_eval", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["attr_chain_eval"] = module
    spec.loader.exec_module(module)

    named = {name for name in module.CHECK_TO_ITEM.values() if name}
    assert named <= set(attribute.ITEMS), sorted(named - set(attribute.ITEMS))
    assert named <= set(attribute.ITEM_PATHS.values()), \
        sorted(named - set(attribute.ITEM_PATHS.values()))


def test_the_five_new_items_attribute_to_their_own_files():
    cases = {
        "usagectl/reports/daily.py": "dates",
        "docs/reports/daily.md": "dates",
        "usagectl/reports/accounts.py": "accounts",
        "usagectl/reports/months.py": "months",
        "usagectl/config.py": "limit",
        "config.sample.json": "limit",
        "docs/readers/sjs.md": "dropped",
    }
    for path, item in cases.items():
        assert attribute.attribute_call([path]) == item, path


def test_the_longer_prefix_still_wins_over_the_older_entries():
    """`usagectl/reports/` 는 summary 이고 그 안의 셋은 각자 자기 항목이다."""
    assert attribute.attribute_call(["usagectl/reports/summary.py"]) == "summary"
    assert attribute.attribute_call(["usagectl/reports/months.py"]) == "months"
    assert attribute.attribute_call(["docs/reports/summary.md"]) == "summary"
    assert attribute.attribute_call(["docs/reports/accounts.md"]) == "accounts"


def test_the_settled_adapter_stays_out_of_the_dropped_item():
    """12번은 어댑터를 고칠 일이 없다. 그 파일은 탐지기의 미끼로 남는다."""
    assert attribute.attribute_call(["usagectl/readers/sjs.py"]) != "dropped"


def test_two_items_that_share_a_file_cannot_be_separated_by_path():
    """**넣어도 다 갈리지는 않는다.** 8번과 10번이 `docs/limits.md`를 같이 쓴다.

    이 한계는 보고에 적는다. 파일이 아니라 항목마다 자기 자리를 갖게 하는
    것이 근본 해결이고, 그것이 `pilot/tasks/subsystems/`의 설계다.
    """
    assert attribute.attribute_call(["docs/limits.md"]) == "docs"
