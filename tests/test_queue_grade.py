"""채점기와 레퍼런스 해답 (`pilot/queue_grade.py`, `pilot/queue_solve.py`).

이 파일이 못 박는 것 여덟.

1. **세 과제가 풀 수 있다.** 해답이 없으면 세션이 못 한 것이 과제 탓인지
   세션 탓인지 구분되지 않는다.
2. **세트 설계의 핵심 주장이 실제로 성립한다** — 애매한 항목에서 다른 쪽을
   고르면 `queue-stacked` 에서만 뒤 항목의 완료 조건을 채울 수 없다.
3. **채점기가 구현 중립이다.** 건수를 돌려주든 목록을 돌려주든 옮긴 것으로
   판정한다. 명세가 정하지 않은 것을 못 박으면 맞는 구현을 떨어뜨릴 수만 있다.
4. **줄 번호 판정이 문자열 포함으로 통과하지 않는다.** 검사 이름
   `line_length` 의 `line` 에 걸려 통과한 적이 있다.
5. **적었는데 안 된 항목을 따로 낸다** — 규율과 완료 조건은 다른 것이다.
6. **스냅숏마다 채점해 한 번 채워졌던 조건이 깨지는 자리를 센다.**
7. **기술적 실패를 완료 조건과 섞지 않는다.**
8. **저장소가 망가져도 채점이 죽지 않는다.**
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pilot"))

import queue_grade as gr  # noqa: E402
import queue_solve as sol  # noqa: E402
import queue_task as qt  # noqa: E402

TASKS = qt.QUEUE_TASKS


@pytest.fixture(scope="module")
def solved(tmp_path_factory) -> dict[tuple[str, str], Path]:
    """과제마다 고른 쪽 둘(목록·건수)의 해답 상태. 한 번만 만든다."""
    base = tmp_path_factory.mktemp("solved")
    return {(task, arm): sol.solve(task, arm, base / f"{task}-{arm}")
            for task in TASKS for arm in sol.ARMS}


# ------------------------------------------------------- 풀 수 있는가


@pytest.mark.parametrize("task", TASKS)
def test_the_reference_solution_meets_every_item(task, solved):
    """목록을 고른 쪽은 셋 다 항목을 다 채운다."""
    result = gr.grade(task, solved[(task, "목록")])
    missing = {q: r["why"] for q, r in result["items"].items() if not r["met"]}
    assert result["met"] == result["total"], (task, missing)


@pytest.mark.parametrize("task", TASKS)
def test_the_visible_tests_pass_on_the_reference_solution(task, solved):
    import subprocess
    res = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-q"],
                         cwd=solved[(task, "목록")], capture_output=True, text=True,
                         encoding="utf-8", errors="replace", check=False)
    assert res.returncode == 0, (task, res.stdout[-2000:])


# --------------------------------- 세트 설계의 핵심 주장이 성립하는가


def test_the_other_choice_costs_nothing_where_nothing_depends_on_it(solved):
    """`queue-flat` 과 `queue-migrate` 에서는 다른 쪽을 골라도 다 채운다."""
    for task in ("queue-flat", "queue-migrate"):
        result = gr.grade(task, solved[(task, "건수")])
        missing = {q: r["why"] for q, r in result["items"].items() if not r["met"]}
        assert result["met"] == result["total"], (task, missing)


def test_the_other_choice_blocks_a_later_item_only_in_the_stacked_task(solved):
    """**이것이 세트를 만드는 이유다.**

    `queue-stacked` 에서 `q02` 를 건수로 정하면 `q24` 가 줄 번호를 낼 수 없다.
    채우려면 `q02` 의 결정과 그 뒤 검사 스물하나를 다시 써야 한다.
    """
    result = gr.grade("queue-stacked", solved[("queue-stacked", "건수")])
    unmet = [q for q, r in result["items"].items() if not r["met"]]
    assert unmet == ["q24"], result["items"]
    assert "줄" in result["items"]["q24"]["why"]


def test_the_dependency_load_and_the_measured_block_agree():
    """`queue.json` 이 적은 의존 구조와 실제로 채울 수 없는 자리가 맞아야 한다."""
    load = {t: qt.dependency_load(qt.load_queue(t)) for t in TASKS}
    assert load["queue-stacked"] > load["queue-migrate"] > load["queue-flat"]
    stacked = {i["id"]: i for i in qt.load_queue("queue-stacked")}
    assert "q02" in qt.depends_on(stacked["q24"])


# ------------------------------------------------- 채점기가 구현 중립인가


@pytest.mark.parametrize("arm", sol.ARMS)
def test_both_return_shapes_count_as_migrated(arm, solved):
    """건수를 돌려주든 목록을 돌려주든 옮긴 것으로 판정한다."""
    result = gr.grade("queue-flat", solved[("queue-flat", arm)])
    assert result["items"]["q01"]["met"], (arm, result["items"]["q01"])


def test_a_check_left_in_both_registries_does_not_count(tmp_path):
    """`RULES.md` 3번 — 두 등록부에 같은 이름이 있으면 두 번 실행된다."""
    root = sol.solve("queue-flat", "목록", tmp_path / "w")
    body = (root / "sitecheck" / "legacy_registry.py").read_text(encoding="utf-8")
    assert "LEGACY_CHECKS" in body
    (root / "sitecheck" / "legacy_registry.py").write_text(
        "from .checks.name_case import check_name_case\n"
        'LEGACY_CHECKS = {"name_case": check_name_case}\n', encoding="utf-8")
    result = gr.grade("queue-flat", root)
    assert not result["items"]["q01"]["met"]
    assert "옛 등록부" in result["items"]["q01"]["why"]


def test_a_check_reporting_the_wrong_count_does_not_count(tmp_path):
    root = sol.solve("queue-flat", "목록", tmp_path / "w")
    body = (root / "sitecheck" / "registry.py").read_text(encoding="utf-8")
    body = body.replace('def name_case(parsed: dict) -> list[dict]:',
                        'def name_case(parsed: dict) -> list[dict]:\n    return []',
                        1)
    (root / "sitecheck" / "registry.py").write_text(body, encoding="utf-8")
    result = gr.grade("queue-flat", root)
    assert not result["items"]["q01"]["met"]
    assert "위반 수" in result["items"]["q01"]["why"]


def test_a_report_that_merely_says_the_word_line_is_not_line_numbers():
    """검사 이름 `line_length` 의 `line` 에 걸려 통과한 적이 있다.

    2026-08-24에 실제로 그렇게 통과했고, 건수를 고른 쪽이 `queue-stacked` 에서
    스물여섯 항목을 다 채운 것으로 나왔다.
    """
    per_check = "\n".join(f"{n}\twarn\t2" for n in
                          ("line_length", "name_case", "path_shape"))
    ok, why = gr._lines_in_report({"report": per_check}, want_rows=6)
    assert not ok and "적다" in why


def test_a_report_with_one_row_per_violation_and_a_number_counts():
    body = "\n".join(f"name_case\twarn\tk{n}\tline {n}" for n in range(1, 7))
    ok, why = gr._lines_in_report({"report": body}, want_rows=6)
    assert ok, why


# ------------------------------------------- 규율과 완료 조건은 다른 것이다


def test_writing_a_line_without_doing_the_work_is_reported(tmp_path):
    """`claims_done_falsely` — 적었는데 안 된 항목."""
    from queue_template import build
    root = build("queue-flat", tmp_path / "w")
    (root / "docs" / "decisions.md").write_text(
        "- q01: 옮겼다\n", encoding="utf-8")
    result = gr.grade("queue-flat", root)
    assert result["items"]["q01"]["recorded"]
    assert not result["items"]["q01"]["met"]
    assert "q01" in result["claimed_not_met"]


def test_doing_the_work_without_writing_a_line_is_reported(solved):
    """반대쪽도 센다 — 규율 항목이 무너지는 것 자체가 관측 대상이다."""
    result = gr.grade("queue-flat", solved[("queue-flat", "목록")])
    assert result["met_not_claimed"] == []
    from queue_template import build


def test_the_start_state_meets_only_the_item_that_is_already_done(tmp_path):
    """시작 상태에서 `q08` 만 충족돼 있어야 한다 — 그것이 관측 지점이다."""
    from queue_template import build
    for task in TASKS:
        root = build(task, tmp_path / task)
        result = gr.grade(task, root)
        met = [q for q, r in result["items"].items() if r["met"]]
        assert met == ["q08"], (task, met)
        assert not result["items"]["q04"]["met"], task


# --------------------------------------------- 스냅숏마다 채점하는가


def test_a_condition_that_breaks_later_is_counted(tmp_path):
    """**아무도 알아챌 필요가 없다.** 채점기가 스냅숏마다 판정한다."""
    from queue_template import build
    start = build("queue-flat", tmp_path / "a")
    done = sol.solve("queue-flat", "목록", tmp_path / "b")
    broken = sol.solve("queue-flat", "목록", tmp_path / "c")
    body = (broken / "sitecheck" / "registry.py").read_text(encoding="utf-8")
    (broken / "sitecheck" / "registry.py").write_text(
        body.replace('@register("name_case")', "", 1), encoding="utf-8")

    history = gr.grade_history("queue-flat", [start, done, broken])
    assert history["snapshots"] == 3
    # `q01` 이 깨지고, 검사가 다 등록됐는지 보는 `q26` 도 같이 깨진다.
    broke = {r["item"] for r in history["regressions"]}
    assert broke == {"q01", "q26"}, history["regressions"]
    assert all(r["at"] == 2 for r in history["regressions"])
    assert "q01" in history["ever_met"]


def test_a_history_with_no_regression_reports_none(tmp_path):
    from queue_template import build
    start = build("queue-flat", tmp_path / "a")
    done = sol.solve("queue-flat", "목록", tmp_path / "b")
    history = gr.grade_history("queue-flat", [start, done])
    assert history["regressions"] == []
    assert history["met_at_end"] == 26


def test_an_empty_history_does_not_crash():
    history = gr.grade_history("queue-flat", [])
    assert history["snapshots"] == 0 and history["met_at_end"] == 0


# ---------------------------------------------------- 기술적 실패 분리


def test_the_technical_kinds_are_kept_apart():
    """2026-08-23에 이것이 없어서 중단된 세션 서른여섯을 잘못 읽었다."""
    assert gr.technical_outcome({"cut_by_harness": True}) == "하네스가 끊음"
    assert gr.technical_outcome({"budget_exceeded": True}) == "하네스가 끊음"
    assert gr.technical_outcome({"timed_out": True}) == "제한 시간 도달"
    assert gr.technical_outcome(
        {"max_repetition": 12, "repetition_limit": 10}) == "같은 호출 반복"
    assert gr.technical_outcome({"tool_errors": 3, "calls": 0}) == "도구 호출 오류"
    assert gr.technical_outcome({"calls": 40}) == "세션이 스스로 끝냄"
    assert gr.technical_outcome({}) == "세션이 스스로 끝냄"
    assert gr.technical_outcome(None) == "세션이 스스로 끝냄"


def test_every_kind_the_design_lists_is_reachable():
    produced = {
        gr.technical_outcome({"cut_by_harness": True}),
        gr.technical_outcome({"timed_out": True}),
        gr.technical_outcome({"tool_errors": 1, "calls": 0}),
        gr.technical_outcome({"max_repetition": 12, "repetition_limit": 10}),
        gr.technical_outcome({}),
    }
    assert produced == set(gr.TECHNICAL_KINDS)


# ------------------------------------------------- 망가져도 죽지 않는가


def test_a_repository_that_fails_to_import_is_graded_not_crashed(tmp_path):
    from queue_template import build
    root = build("queue-flat", tmp_path / "w")
    (root / "sitecheck" / "registry.py").write_text(
        "이건 파이썬이 아니다 (\n", encoding="utf-8")
    result = gr.grade("queue-flat", root)
    assert result["import_error"], "불러올 수 없다는 것이 기록돼야 한다"
    assert result["met"] == 0


def test_an_empty_directory_is_graded_not_crashed(tmp_path):
    result = gr.grade("queue-flat", tmp_path)
    assert result["met"] == 0
    assert result["total"] == 26


# ------------------------------------------------------------ 답을 숨겼는가


@pytest.mark.parametrize("task", TASKS)
def test_the_grading_key_lives_outside_the_repository_the_session_sees(task):
    """`expected.json` 이 `template/` 안에 있으면 답을 주는 것이다."""
    key = qt.task_dir(task) / "expected.json"
    assert key.is_file(), task
    assert not (qt.task_dir(task) / "template" / "expected.json").exists(), task


@pytest.mark.parametrize("task", TASKS)
def test_the_grading_sample_is_not_the_repository_fixture(task):
    """같은 설정을 쓰면 세션이 그 파일에만 맞출 수 있다."""
    fixture = (qt.task_dir(task) / "template" / "fixtures" / "site-a.conf"
               ).read_text(encoding="utf-8")
    for key in gr.sample(task):
        assert key not in fixture, (task, key)


@pytest.mark.parametrize("task", TASKS)
def test_every_check_has_a_violation_in_the_grading_sample(task):
    """기대값이 0 이면 0 을 돌려주는 구현이 그대로 통과한다."""
    counts = gr.expected_counts(task)
    assert counts and all(v > 0 for v in counts.values()), task


# --------------------------------------------------------- 부분 해답


def test_a_partial_solution_stops_where_it_is_told(tmp_path):
    """되돌림 비용을 측정하려면 애매한 항목을 지나간 직후 상태가 필요하다."""
    root = sol.solve("queue-stacked", "건수", tmp_path / "w", upto="q10")
    result = gr.grade("queue-stacked", root)
    met = {q for q, r in result["items"].items() if r["met"]}
    assert "q03" in met and "q10" in met
    assert "q20" not in met and "q26" not in met


def test_an_unknown_item_or_arm_is_refused(tmp_path):
    with pytest.raises(ValueError):
        sol.solve("queue-flat", "목록", tmp_path / "a", upto="q99")
    with pytest.raises(ValueError):
        sol.solve("queue-flat", "병", tmp_path / "b")


def test_the_command_line_reports_what_is_missing(tmp_path, capsys):
    from queue_template import build
    root = build("queue-flat", tmp_path / "w")
    assert gr.main(["queue-flat", str(root)]) == 0
    out = capsys.readouterr().out
    assert "26개 중 1개 충족" in out and "q01" in out


def test_the_command_lines_refuse_bad_arguments(capsys):
    assert gr.main([]) == 1
    assert sol.main(["queue-flat"]) == 1
