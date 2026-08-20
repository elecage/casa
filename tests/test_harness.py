"""Tests for the session harness — the guardrails on our own dev sessions.

The harness exists because this project's documented rules did not hold on
their own: CLAUDE.md has said "update STATUS.md in the same commit" from the
start, and a 7-session collection batch still sat unrecorded for three weeks.
So each test below pins a failure that actually happened, not a hypothetical:

1. the collection lock must block running the session runner while the task
   design question is open, and must NOT block re-analysis or reading files
   (bug fixes and reproduction have to stay possible).
2. the record check must catch a results/ batch that STATUS.md never mentions.
3. the task-design check must reject a new task without a filled-in rubric,
   because both previous pivots produced another "implement one function".
4. the report check must fire on internal labels and undefined stats terms,
   and stay quiet on plain language.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness"))

import check_records  # noqa: E402
import check_task_design  # noqa: E402
import collection_guard  # noqa: E402
import gates  # noqa: E402
import report_check  # noqa: E402
import session_start  # noqa: E402


# --------------------------------------------------------------- gate state


def test_gates_file_is_valid_json_and_declares_collection():
    data = json.loads((ROOT / "harness" / "gates.json").read_text(encoding="utf-8"))
    assert data["collection"]["state"] in {"locked", "open"}
    assert data["collection"]["reason"].strip()
    assert data["collection"]["unlock_requires"].strip()


def test_gate_state_falls_back_when_file_is_missing(tmp_path):
    assert gates.load_gates(tmp_path / "nope.json") == {}
    assert gates.gate_state("collection", {}, default="open") == "open"
    assert gates.gate_state("collection", {"collection": {"state": "locked"}}) == "locked"


# ---------------------------------------------------------- collection lock


@pytest.mark.parametrize(
    "command",
    [
        ".venv/Scripts/python.exe pilot/run_sessions.py pilot/tasks/ml-shift -n 30",
        ".venv/bin/python pilot/run_sessions.py pilot/tasks/schedule -n 5 --model haiku",
        "python3 pilot/run_sessions.py x",
    ],
)
def test_collection_run_is_recognised(command):
    assert collection_guard.is_collection_run("Bash", {"command": command})


@pytest.mark.parametrize(
    "command",
    [
        ".venv/Scripts/python.exe -u pilot/run_sessions.py x",
        "py -3 pilot/run_sessions.py pilot/tasks/orbit-propagator -n 2",
    ],
)
def test_collection_run_is_recognised_with_flags(command):
    assert collection_guard.is_collection_run("Bash", {"command": command})


@pytest.mark.parametrize(
    "command",
    [
        "cat pilot/run_sessions.py",
        "grep -n ensure_task_venv pilot/run_sessions.py",
        ".venv/Scripts/python.exe pilot/analysis/ability_early.py results/main2/orbit-sonnet",
        ".venv/Scripts/python.exe -m pytest",
        "git log --oneline",
    ],
)
def test_non_collection_commands_pass(command):
    assert not collection_guard.is_collection_run("Bash", {"command": command})


@pytest.mark.parametrize(
    "command",
    [
        # 오탐 1: `.py` 확장자의 py를 인터프리터로 오인했다. 이 기능의 PR
        # 본문이 첫 피해자였다 — 러너를 설명하기만 해도 차단됐다.
        'gh pr create --body "수집 잠금은 pilot/run_sessions.py 실행을 차단한다"',
        "ls -la pilot/run_sessions.py",
        # 오탐 2: 커밋 메시지가 실행 형태를 인용했을 뿐인데 걸렸다. 그 수정
        # 커밋이 두 번째 피해자였다.
        'git commit -m "우회 구멍이었다: find -exec python run_sessions.py"',
        'echo "실행법은 python pilot/run_sessions.py <task> -n 30 이다"',
    ],
)
def test_merely_mentioning_the_runner_is_not_blocked(command):
    assert not collection_guard.is_collection_run("Bash", {"command": command})


def test_quoted_path_is_still_a_real_invocation():
    """산문은 지우되 인용된 '경로'는 남긴다 — 공백 유무로 가른다."""
    assert collection_guard.is_collection_run(
        "Bash", {"command": 'python "pilot/run_sessions.py" -n 5'}
    )
    assert collection_guard.strip_prose_quotes('a "긴 산문 이다" b') == "a   b"
    assert collection_guard.strip_prose_quotes('a "짧은것" b') == 'a "짧은것" b'


def test_non_shell_tools_are_never_blocked():
    assert not collection_guard.is_collection_run(
        "Read", {"file_path": "pilot/run_sessions.py"}
    )


def _run(script: str, stdin: str) -> subprocess.CompletedProcess:
    """Hook messages are UTF-8; Windows would otherwise decode them as cp949."""
    return subprocess.run(
        [sys.executable, str(ROOT / "harness" / script)],
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _run_guard(payload: dict) -> subprocess.CompletedProcess:
    return _run("collection_guard.py", json.dumps(payload))


def test_guard_blocks_collection_while_locked():
    """End-to-end: exit 2 is what actually stops the tool call."""
    if gates.gate_state("collection") != "locked":
        pytest.skip("collection gate is open; block path not applicable")
    res = _run_guard(
        {"tool_name": "Bash", "tool_input": {"command": "python pilot/run_sessions.py x"}}
    )
    assert res.returncode == 2
    assert "잠금" in res.stderr


def test_guard_allows_analysis_even_while_locked():
    res = _run_guard(
        {
            "tool_name": "Bash",
            "tool_input": {"command": "python pilot/analysis/signal_validation.py results/"},
        }
    )
    assert res.returncode == 0


def test_guard_survives_garbage_input():
    assert _run("collection_guard.py", "not json at all").returncode == 0


# ------------------------------------------------------------- session start


def test_session_start_emits_goal_and_lock_state():
    out = session_start.render(
        gates.load_gates(), (ROOT / "harness" / "anchor.md").read_text(encoding="utf-8")
    )
    assert "능력" in out and "조기" in out
    assert "collection" in out


def test_session_start_reports_a_broken_gate_file():
    out = session_start.render({}, "# anchor\n")
    assert "확인할 것" in out


# ------------------------------------------------------------ record keeping


def test_status_required_when_work_paths_change():
    assert check_records.needs_status(["src/casa/metrics.py"])
    assert check_records.needs_status(["pilot/tasks/ml-shift/grade.py", "README.md"])
    assert not check_records.needs_status(["src/casa/metrics.py", "STATUS.md"])
    assert not check_records.needs_status(["docs/RESEARCH_PLAN.md"])


def test_unrecorded_batch_is_reported(tmp_path):
    root = tmp_path / "results"
    (root / "main2" / "orbit-sonnet").mkdir(parents=True)
    (root / "main2" / "ml-shift-sonnet").mkdir(parents=True)
    status = "orbit-sonnet 60세션 수집 완료."
    assert check_records.unrecorded_batches(root, status) == ["main2/ml-shift-sonnet"]


def test_all_batches_recorded_is_clean(tmp_path):
    root = tmp_path / "results"
    (root / "cal" / "tabular-b").mkdir(parents=True)
    assert check_records.unrecorded_batches(root, "tabular-b 프로브 0/3") == []


def test_missing_results_dir_is_not_an_error(tmp_path):
    assert check_records.unrecorded_batches(tmp_path / "results", "") == []


# ------------------------------------------------------------- task design


FILLED = """# 설계 검문

## 1. 판단 단계
세션이 두 문서 중 어느 쪽이 최신인지 스스로 판정해야 한다.

## 2. 상충 요구
README는 반올림을, 스키마는 버림을 요구한다. 둘 다 만족시킬 수 없다.

## 3. 기존 상태와의 정합
커밋 로그에 절반만 적용된 이름 변경이 남아 있다.

## 4. 애매함
프롬프트는 어느 문서를 따를지 말하지 않는다.

## 5. 길이와 규율
여섯 단계이며 마지막 두 단계에서 기록 갱신이 요구된다.

## 6. 채점 환원
해석 A는 out.json의 total을 1000으로, 해석 B는 999로 만든다. 값 하나로 갈린다.

## 7. 기술적 실패 분리
채점기가 산출물 없음·시간 초과·동일 호출 반복을 별도 코드로 내보낸다.

## 8. 과정 채점
세션 점수는 최종 산출물이 아니라 빠진 함정 수로 매긴다. 있는 함수를 다시
구현하는 함정과 조기 포기 함정을 심었고, 안 빠짐·회복·빠진 채 종료를
따로 기록한다. 통과/실패는 부수 기록으로만 남긴다.
"""


def test_filled_design_passes():
    assert check_design_ok(FILLED)


def test_process_scoring_section_is_required():
    """8번(과정 채점)이 없으면 거부된다.

    이 항목이 없던 동안 검문은 과제가 결과 채점으로 되돌아가는 것을 막지
    못했고, 2026-08-20에 실제로 되돌아갔다.
    """
    without = FILLED[: FILLED.index("## 8. 과정 채점")] + '"""'
    problems = check_task_design.check_design(without)
    assert any("8." in p for p in problems)


def check_design_ok(text: str) -> bool:
    return check_task_design.check_design(text) == []


def test_missing_section_is_caught():
    text = FILLED.replace("## 6. 채점 환원", "## 6x. 채점 환원")
    problems = check_task_design.check_design(text)
    assert any("6." in p for p in problems)


def test_empty_and_placeholder_sections_are_caught():
    empty = FILLED.replace("세션이 두 문서 중 어느 쪽이 최신인지 스스로 판정해야 한다.", "")
    assert any("1." in p for p in check_task_design.check_design(empty))

    todo = FILLED.replace(
        "프롬프트는 어느 문서를 따를지 말하지 않는다.", "TODO: 나중에 적는다"
    )
    assert any("4." in p for p in check_task_design.check_design(todo))


def test_new_task_without_design_is_rejected(tmp_path):
    tasks = tmp_path / "tasks"
    (tasks / "legacy-one").mkdir(parents=True)
    (tasks / "brand-new").mkdir(parents=True)
    findings = check_task_design.audit_tasks(tasks, {"legacy-one"})
    assert list(findings) == ["brand-new"]
    assert "DESIGN.md" in findings["brand-new"][0]


def test_new_task_with_filled_design_is_accepted(tmp_path):
    tasks = tmp_path / "tasks"
    task = tasks / "state-reconcile"
    task.mkdir(parents=True)
    (task / "DESIGN.md").write_text(FILLED, encoding="utf-8")
    assert check_task_design.audit_tasks(tasks, set()) == {}


def test_legacy_allowlist_is_frozen_and_matches_real_dirs():
    """The exemption is grandfathering, not a door new tasks can walk through."""
    legacy = check_task_design.load_legacy(ROOT / "harness" / "legacy_tasks.txt")
    assert len(legacy) == 11, "legacy allowlist must not grow — new tasks need DESIGN.md"
    for name in legacy:
        assert (ROOT / "pilot" / "tasks" / name).is_dir(), f"stale exemption: {name}"


# ----------------------------------------------------------- report discipline


def test_internal_labels_are_detected_through_korean_particles():
    """Regression: \\b sees Hangul as a word char, so "F1이"/"W15에" slipped past."""
    hits = report_check.find_internal_labels("RQ2 재계산 결과 F1이 뒤집혔고 W15에 적었다")
    assert set(hits) == {"RQ2", "F1", "W15"}


def test_f1_score_is_not_flagged_as_an_internal_label():
    assert report_check.find_internal_labels("F1 스코어가 0.8로 올랐다") == []
    assert report_check.find_internal_labels("the F1 score improved") == []


def test_undefined_stats_terms_are_detected():
    assert report_check.find_undefined_stats("판별력은 AUROC 0.66 수준이었다") == ["AUROC"]


def test_defined_stats_terms_are_allowed():
    text = "판별력(AUROC = 성공/실패를 가르는 힘, 0.5는 동전던지기)은 0.66이었다"
    assert report_check.find_undefined_stats(text) == []


def test_plain_language_report_is_clean():
    text = (
        "실패한 세션 55건 중 53건이 '다 했다'고 보고했습니다. "
        "재현: casa report results/main2/orbit-sonnet --tasks-root pilot/tasks"
    )
    assert report_check.find_internal_labels(text) == []
    assert report_check.find_undefined_stats(text) == []


def _run_report_check(payload: dict) -> subprocess.CompletedProcess:
    return _run("report_check.py", json.dumps(payload))


def test_report_check_blocks_jargon_once_then_stays_quiet():
    payload = {
        "session_id": "pytest-report-check",
        "last_assistant_message": "RQ2와 F1 기준으로 AUROC가 올랐습니다",
    }
    marker = report_check._marker(payload["session_id"])
    marker.unlink(missing_ok=True)
    try:
        first = _run_report_check(payload)
        assert first.returncode == 2
        assert "내부 라벨" in first.stderr
        second = _run_report_check(payload)
        assert second.returncode == 0, "must not loop — one block per session"
    finally:
        marker.unlink(missing_ok=True)


def test_report_check_does_not_block_a_continued_turn():
    res = _run_report_check(
        {
            "session_id": "pytest-stop-active",
            "stop_hook_active": True,
            "last_assistant_message": "RQ2와 F1 기준으로 AUROC가 올랐습니다",
        }
    )
    assert res.returncode == 0


def test_every_pilot_runner_is_covered_by_the_lock():
    """A new runner must not slip past the collection lock.

    This happened: `run_chain.py` was added and the guard still only knew
    about `run_sessions.py`, so chain collection bypassed the lock entirely.
    Deriving the check from the filesystem makes the next one fail loudly.
    """
    runners = {p.name for p in (ROOT / "pilot").glob("run_*.py")}
    assert runners, "no runners found — the glob is wrong, not the guard"
    assert runners <= set(collection_guard.RUNNERS), (
        f"러너가 잠금 목록에 없다: {sorted(runners - set(collection_guard.RUNNERS))}")


@pytest.mark.parametrize("runner", ["run_sessions.py", "run_chain.py"])
def test_each_runner_is_recognised_as_collection(runner):
    command = f".venv/Scripts/python.exe pilot/{runner} pilot/tasks/casefile -n 3"
    assert collection_guard.is_collection_run("Bash", {"command": command})
