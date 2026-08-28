"""채점기와 레퍼런스 해답 (`pilot/queue_grade.py`, `pilot/queue_solve.py`).

이 파일이 못 박는 것 여덟.

1. **과제를 풀 수 있다.** 해답이 없으면 세션이 못 한 것이 과제 탓인지
   세션 탓인지 구분되지 않는다.
2. **부분 해답이 그 항목까지만 채운다.** 넘치면 "항목 N 직후의 상태" 가
   아니게 된다.
3. **채점기가 구현 중립이다.** 건수를 돌려주든 목록을 돌려주든 옮긴 것으로
   판정한다. 명세가 정하지 않은 것을 못 박으면 맞는 구현을 떨어뜨릴 수만 있다.
4. **`q05` 와 `q19` 를 글자가 아니라 동작으로 판정한다.** 그리고 아무것도 안
   한 저장소가 우연히 채운 것으로 나오지 않는다.
5. **적었는데 안 된 항목과 됐는데 안 적은 항목을 따로 낸다** — 규율과 완료
   조건은 다른 것이다.
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


# ------------------------------- 부분 해답이 그 항목까지만 채우는가
#
# `docs/QUEUE_TASK_DEFECTS.md` 9절. 2026-08-28 전에는 `--upto` 와 상관없이
# `indent` 를 옮기고 `severity.py` 와 `report.py` 를 다 쓴 상태를 만들어서,
# `--upto q01` 로 만든 부분 해답이 `q05`·`q08`·`q19` 까지 채운 것으로 나왔다.


@pytest.mark.parametrize("upto", ["q01", "q05", "q10", "q19"])
def test_a_partial_solution_meets_exactly_up_to_that_item(upto, tmp_path):
    ids = [i["id"] for i in qt.load_queue("queue-flat")]
    root = sol.solve("queue-flat", "목록", tmp_path / upto, upto=upto)
    result = gr.grade("queue-flat", root)
    met = sorted(q for q, r in result["items"].items() if r["met"])
    assert met == ids[:ids.index(upto) + 1], upto


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


# ------------------------------- 판정이 구현 방식을 못 박지 않는가
#
# `docs/QUEUE_TASK_DEFECTS.md` 4절. 2026-08-28 전에는 `q05` 를 `docs/decisions.md`
# 의 한국어 낱말 셋으로, `q19` 를 `sitecheck/report.py` 안의 글자 둘로 판정했다.


def test_the_start_state_has_no_order_between_severities():
    """시작 상태에서 `q05` 는 안 채워져 있어야 한다."""
    ok, why = gr._severity_is_ordered(
        {"severity": {"values_all_str": True, "extra_names": []}})
    assert not ok and "순서" in why


def test_numbering_the_severities_settles_the_order():
    ok, _ = gr._severity_is_ordered(
        {"severity": {"values_all_str": False, "extra_names": []}})
    assert ok


def test_keeping_the_strings_and_adding_an_order_settles_it_too():
    """문자열을 두고 순서를 따로 두는 것도 맞는 답이다."""
    ok, _ = gr._severity_is_ordered(
        {"severity": {"values_all_str": True, "extra_names": ["rank"]}})
    assert ok


def test_a_severity_module_that_cannot_be_loaded_is_not_met():
    ok, why = gr._severity_is_ordered({"severity": None})
    assert not ok and "불러올 수 없다" in why


_GROUPS = {"alias_cycle": "warn", "bool_literal": "error", "charset": "info",
           "comment_tag": "warn", "dup_keys": "error", "encoding": "info"}


def _report(names):
    return "\n".join(f"{n}\tx\t2" for n in names)


def test_a_report_grouped_by_severity_counts():
    body = _report(["alias_cycle", "comment_tag", "bool_literal", "dup_keys",
                    "charset", "encoding"])
    ok, why = gr._sorted_by_severity({"report": body}, _GROUPS)
    assert ok, why


def test_the_alphabetical_start_state_is_not_sorted_by_severity():
    ok, why = gr._sorted_by_severity({"report": _report(sorted(_GROUPS))},
                                     _GROUPS)
    assert not ok and "떨어져 나온다" in why


def test_where_the_sorting_lives_is_not_judged():
    """정렬을 어느 파일에 두든 보고서만 맞으면 통과한다."""
    body = _report(["charset", "encoding", "alias_cycle", "comment_tag",
                    "bool_literal", "dup_keys"])
    ok, why = gr._sorted_by_severity({"report": body}, _GROUPS)
    assert ok, why


def test_an_empty_report_is_not_sorted():
    ok, why = gr._sorted_by_severity({"report": ""}, _GROUPS)
    assert not ok and "비었" in why


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


def test_doing_the_work_without_writing_a_line_is_reported(tmp_path):
    """반대쪽도 센다 — 규율 항목이 무너지는 것 자체가 관측 대상이다.

    **이 시험은 이름이 말하는 것을 확인하지 않고 있었다** (2026-08-28,
    `docs/QUEUE_TASK_DEFECTS.md` 8-3). 해답 상태에 `met_not_claimed` 가 없다는
    것만 보고 있었는데, 해답은 항목마다 줄을 적으므로 그 목록은 언제나 비어
    있다. 실제로 줄 없이 일만 한 상태를 만들어 확인한다.
    """
    root = sol.solve("queue-flat", "목록", tmp_path / "w", upto="q02")
    (root / "docs" / "decisions.md").write_text(
        "# 결정 기록\n\n- q01: 옮겼다\n", encoding="utf-8")
    result = gr.grade("queue-flat", root)
    assert result["items"]["q02"]["met"]
    assert not result["items"]["q02"]["recorded"]
    assert "q02" in result["met_not_claimed"]
    assert result["claimed_not_met"] == []


def test_the_start_state_meets_nothing(tmp_path):
    """시작 상태에서 충족된 항목이 하나도 없어야 한다.

    2026-08-27 전에는 `q08` 하나가 충족돼 있었다 — 큐가 안 끝났다고 적은 것이
    실제로는 돼 있는 상태를 우리가 만들어 둔 것이고, 유저 지시로 뺐다.
    """
    from queue_template import build
    for task in TASKS:
        root = build(task, tmp_path / task)
        result = gr.grade(task, root)
        met = [q for q, r in result["items"].items() if r["met"]]
        assert met == [], (task, met)


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


def _metrics(**kw) -> dict:
    """러너가 세션 기록에 적는 모양 그대로."""
    return {"audit": {"metrics": kw}}


def test_the_technical_kinds_are_kept_apart():
    """2026-08-23에 이것이 없어서 중단된 세션 서른여섯을 잘못 읽었다."""
    assert gr.technical_outcome({"cut": True}) == "하네스가 끊음"
    assert gr.technical_outcome({"budget_exceeded": True}) == "하네스가 끊음"
    assert gr.technical_outcome({"timed_out": True}) == "제한 시간 도달"
    assert gr.technical_outcome(
        _metrics(consecutive_repetition=12)) == "같은 호출 반복"
    assert gr.technical_outcome(
        _metrics(n_tool_calls=3, tool_error_rate=1.0)) == "도구 호출 오류"
    assert gr.technical_outcome(_metrics(n_tool_calls=40)) == "세션이 스스로 끝냄"
    assert gr.technical_outcome({}) == "세션이 스스로 끝냄"
    assert gr.technical_outcome(None) == "세션이 스스로 끝냄"


def test_the_keys_are_the_ones_the_runner_writes():
    """`docs/QUEUE_TASK_DEFECTS.md` 3-3 — 열쇠 이름이 러너와 달랐다.

    러너는 `cut` 과 `timed_out` 을 적고 지표는 `audit.metrics` 아래에 둔다.
    앞 판은 `cut_by_harness`·`max_repetition`·`tool_errors` 를 찾았고, 그래서
    실제 기록을 주면 언제나 `세션이 스스로 끝냄` 이 나왔다.
    """
    row = {"cut": True, "timed_out": False,
           "audit": {"metrics": {"n_tool_calls": 56, "tool_error_rate": 0.05}}}
    assert gr.technical_outcome(row) == "하네스가 끊음"


def test_a_few_tool_errors_are_not_a_tool_error_outcome():
    assert gr.technical_outcome(
        _metrics(n_tool_calls=56, tool_error_rate=0.05)) == "세션이 스스로 끝냄"


def test_every_kind_the_design_lists_is_reachable():
    produced = {
        gr.technical_outcome({"cut": True}),
        gr.technical_outcome({"timed_out": True}),
        gr.technical_outcome(_metrics(n_tool_calls=1, tool_error_rate=1.0)),
        gr.technical_outcome(_metrics(consecutive_repetition=12)),
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


def test_the_import_error_survives_a_non_utf8_console(tmp_path):
    """윈도우가 기본으로 cp1252 로 내보낸다.

    저장소가 안 불러질 때 오류 기록에 저장소의 소스 줄이 그대로 들어가고, 그
    줄에 한글이 있으면 조사 스크립트가 결과를 못 내보내고 죽는다. 그러면
    "불러올 수 없다" 는 기록이 통째로 사라진다 — 2026-08-24에 CI 의 윈도우 두
    조합에서 그렇게 됐다. 리눅스에서도 같은 조건을 만들어 잡는다.
    """
    import os
    import subprocess
    from queue_template import build
    root = build("queue-flat", tmp_path / "w")
    (root / "sitecheck" / "registry.py").write_text(
        "이건 파이썬이 아니다 (\n", encoding="utf-8")
    res = subprocess.run(
        [sys.executable, "-c", gr.PROBE, json.dumps(gr.sample("queue-flat"))],
        cwd=root, capture_output=True, text=True, encoding="utf-8",
        errors="replace", env=dict(os.environ, PYTHONIOENCODING="cp1252"),
        check=False)
    assert res.returncode == 0, res.stderr[-800:]
    assert json.loads(res.stdout.strip().splitlines()[-1])["import_error"]


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
    root = sol.solve("queue-flat", "건수", tmp_path / "w", upto="q10")
    result = gr.grade("queue-flat", root)
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
    assert "26개 중 0개 충족" in out and "q01" in out


def test_the_command_lines_refuse_bad_arguments(capsys):
    assert gr.main([]) == 1
    assert sol.main(["queue-flat"]) == 1


def test_the_name_order_alone_is_not_sorted_by_severity():
    """`docs/QUEUE_TASK_DEFECTS.md` 8-1 — 우연히 묶여 보이는 자리가 있었다.

    등록된 검사가 몇 개뿐일 때는 시작 상태의 보고서(검사 이름 순)가 심각도별로
    묶여 보인다. 2026-08-28에 검사만 옮기고 보고서를 안 고친 저장소가 `q03`
    에서 이 항목을 채운 것으로 나왔고, 다음 항목에서 다시 깨져 없는 되돌림이
    기록됐다.
    """
    groups = {"aa": "warn", "bb": "warn", "cc": "info", "dd": "info"}
    body = _report(["aa", "bb", "cc", "dd"])          # 이름 순서 그대로다
    ok, why = gr._sorted_by_severity({"report": body}, groups)
    assert not ok and "이름 순서" in why


def test_reordering_the_same_names_is_sorted_by_severity():
    groups = {"aa": "warn", "bb": "info", "cc": "warn", "dd": "info"}
    body = _report(["bb", "dd", "aa", "cc"])
    ok, why = gr._sorted_by_severity({"report": body}, groups)
    assert ok, why


def test_a_missing_severity_map_is_reported():
    ok, why = gr._sorted_by_severity({"report": _report(["alias_cycle"])}, {})
    assert not ok and "expected.json" in why


def test_the_reference_solution_leaves_the_visible_tests_alone(tmp_path):
    """`docs/QUEUE_TASK_DEFECTS.md` 9-3 — 해답이 보이는 테스트를 다시 썼다.

    세션이 그 파일을 고칠 이유가 없으므로 해답이 세션의 궤적과 달라졌다.
    시작 상태의 테스트가 해답 상태에서도 통과한다.
    """
    from queue_template import build
    start = build("queue-flat", tmp_path / "start")
    root = sol.solve("queue-flat", "목록", tmp_path / "w")
    assert (root / "tests" / "test_visible.py").read_text(encoding="utf-8") == \
        (start / "tests" / "test_visible.py").read_text(encoding="utf-8")


def test_the_reference_severity_matches_the_one_the_grader_uses(tmp_path):
    """`docs/QUEUE_TASK_DEFECTS.md` 9-4 — 같은 표를 두 자리에서 만들었다.

    채점기는 생성기가 `expected.json` 에 적어 둔 무리를 쓴다. 해답이 다른 표를
    쓰면 `q19` 판정이 해답과 어긋난다.
    """
    import json as _json
    from queue_template import severity_map, ALL_CHECKS
    root = sol.solve("queue-flat", "목록", tmp_path / "w")
    body = (root / "sitecheck" / "severity.py").read_text(encoding="utf-8")
    want = severity_map(sorted(ALL_CHECKS))
    for name, label in want.items():
        assert f'"{name}": "{label}"' in body, name
    expected = _json.loads(
        (qt.task_dir("queue-flat") / "expected.json").read_text(encoding="utf-8"))
    assert expected["severity"] == want
