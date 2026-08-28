"""사슬 러너와 큐 과제 셋의 연결 (`pilot/run_chain.py`, `pilot/queue_hook.py`,
`pilot/queue_history.py`).

**무엇이 없어서 안 돌았나.** `pilot/run_chain.py` 는 과제 디렉토리에서
`relevant_files.txt` 와 `grade.py` 를 찾고, 채점기 출력에서 `milestone_score`
를 읽는다. 큐 과제 셋은 셋 다 갖고 있지 않았다. 그리고 `NEXT.md` 는 세션이
`docs/decisions.md` 에 줄을 적을 때마다 다시 써져야 하는데, 그것을 부르는
자리가 시험과 명령줄 진입점뿐이었다 — 세션 하나가 항목 하나밖에 못 한다.

이 파일이 못 박는 것 다섯.

1. **생성기가 러너가 찾는 둘을 만든다** — `grade.py`, `relevant_files.txt`.
2. **`grade.py` 는 ASCII 로만 내보낸다.** 못 채운 이유가 한글이고, 윈도우
   기본 인코딩이 그것을 못 내보내면 채점 출력이 통째로 사라진다.
3. **`NEXT.md` 갱신 훅이 스냅숏 훅을 지우지 않는다.** 둘 다 `PostToolUse` 다.
4. **줄을 적으면 다음 항목이 드러난다.**
5. **호출별 스냅숏이 `grade_history` 로 들어간다** — 채웠다 깨진 자리가 잡힌다.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pilot"))

import queue_history  # noqa: E402
import queue_hook  # noqa: E402
import queue_task as qt  # noqa: E402
import queue_template as tpl  # noqa: E402
import run_chain  # noqa: E402
import snapshot  # noqa: E402

TASK = "queue-flat"


# ------------------------------------------------- 러너가 찾는 파일 둘


@pytest.mark.parametrize("task", qt.QUEUE_TASKS)
def test_every_queue_task_has_what_the_chain_runner_looks_for(task):
    task_dir = qt.task_dir(task)
    for name in ("prompt.txt", "prompt_followup.txt", "grade.py",
                 "relevant_files.txt", "expected.json"):
        assert (task_dir / name).is_file(), f"{task}: {name}"


def test_relevant_files_covers_every_file_the_queue_names():
    """큐에서 뽑는다. 따로 적어 두면 큐가 바뀔 때 조용히 어긋난다."""
    listed = set((qt.task_dir(TASK) / "relevant_files.txt").read_text(
        encoding="utf-8").split())
    for item in qt.load_queue(TASK):
        for rel in item["relevant"]:
            assert rel in listed, rel
    for always in qt.ALWAYS_EDITABLE:
        assert always in listed, always


def test_the_grade_entry_point_prints_ascii_only_json(tmp_path):
    """못 채운 이유가 한글이다. 윈도우 기본 인코딩이 그것을 못 내보낸다."""
    work = tmp_path / "work"
    tpl.build(TASK, work)
    done = subprocess.run(
        [sys.executable, str(qt.task_dir(TASK) / "grade.py"), str(work)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        check=False)
    assert done.returncode == 0, done.stderr[-2000:]
    done.stdout.encode("ascii")          # 여기서 터지면 윈도우에서 사라진다
    result = json.loads(done.stdout)
    assert result["task"] == TASK and result["total"] == len(qt.load_queue(TASK))


# ------------------------------------------------- 채점기 출력 읽기


def test_the_runner_reads_both_grader_shapes():
    """옛 과제는 `milestone_score`, 큐 과제 셋은 `met` 이다."""
    assert run_chain.progress_of({"milestone_score": 7}) == 7
    assert run_chain.progress_of({"met": 3, "total": 26}) == 3
    assert run_chain.progress_of({"parse_error": True}) is None
    assert run_chain.progress_of({}) is None


def test_the_progress_line_names_what_it_counted():
    old = run_chain.progress_line({"milestone_score": 7, "violations": 1})
    assert "마일스톤 7" in old and "위반 1" in old
    new = run_chain.progress_line(
        {"met": 3, "total": 26, "claimed_not_met": ["q04"]})
    assert "충족 3/26" in new and "적었는데 안 된 항목 1" in new
    assert run_chain.progress_line({"parse_error": True}) == "채점 결과 없음"


# ------------------------------------------------- NEXT.md 갱신 훅


def _install_both(work: Path, git_dir: Path) -> dict:
    snapshot.install(work, git_dir)
    queue_hook.install(work, TASK)
    return json.loads((work / ".claude" / "settings.json").read_text(
        encoding="utf-8"))


def test_the_queue_hook_keeps_the_snapshot_hook(tmp_path):
    """둘 다 `PostToolUse` 다. 뒤에 배선하는 쪽이 앞의 것을 지우면 안 된다."""
    work = tmp_path / "work"
    tpl.build(TASK, work)
    settings = _install_both(work, tmp_path / "snap.git")
    commands = [h["command"] for entry in settings["hooks"]["PostToolUse"]
                for h in entry["hooks"]]
    assert any("queue_hook.py" in c for c in commands)
    assert any("snapshot.py" in c for c in commands)
    # 갱신된 NEXT.md 가 이번 호출의 스냅숏에 담기도록 앞에 온다.
    assert "queue_hook.py" in commands[0]


def test_installing_twice_does_not_stack_the_same_hook(tmp_path):
    """사슬은 세션마다 배선한다."""
    work = tmp_path / "work"
    tpl.build(TASK, work)
    _install_both(work, tmp_path / "snap.git")
    settings = _install_both(work, tmp_path / "snap.git")
    commands = [h["command"] for entry in settings["hooks"]["PostToolUse"]
                for h in entry["hooks"]]
    assert sum("queue_hook.py" in c for c in commands) == 1


def test_writing_a_decision_line_reveals_the_next_item(tmp_path):
    work = tmp_path / "work"
    tpl.build(TASK, work)
    queue_hook.install(work, TASK)
    first = (work / "NEXT.md").read_text(encoding="utf-8")
    assert "## q01" in first

    decisions = work / "docs" / "decisions.md"
    decisions.write_text(decisions.read_text(encoding="utf-8")
                         + "\n- q01: 옮겼다\n", encoding="utf-8")
    queue_hook.refresh(work)
    second = (work / "NEXT.md").read_text(encoding="utf-8")
    assert "## q02" in second and "## q01" not in second


def test_the_hook_does_nothing_where_there_is_no_queue(tmp_path):
    assert queue_hook.refresh(tmp_path) is None


# ------------------------------------------------- 스냅숏 -> grade_history


def _snapshot_run(work: Path, git_dir: Path, edits: list[tuple[str, str]]) -> None:
    """편집마다 스냅숏을 한 번 찍는다. 세션이 호출마다 하는 것과 같다."""
    snapshot.install(work, git_dir)
    for rel, text in edits:
        (work / rel).write_text(text, encoding="utf-8")
        snapshot.take(work)


def test_snapshots_reach_grade_history_and_a_broken_item_is_counted(tmp_path):
    """채웠다가 깨진 자리를 센다. 끝 상태만 보면 안 빠진 세션과 같아 보인다."""
    work = tmp_path / "work"
    tpl.build(TASK, work)
    git_dir = tmp_path / "snap.git"

    registry = (work / "sitecheck" / "registry.py").read_text(encoding="utf-8")
    moved = registry + (
        '\n\n@register("name_case")\n'
        'def name_case(parsed):\n'
        '    from .checks.name_case import check_name_case\n'
        '    return check_name_case(parsed)\n')
    legacy = (work / "sitecheck" / "legacy_registry.py").read_text(
        encoding="utf-8")
    without = legacy.replace(
        '    "name_case": check_name_case,\n', "")
    assert without != legacy, "옛 등록부에서 그 줄을 못 찾았다"

    _snapshot_run(work, git_dir, [
        ("sitecheck/legacy_registry.py", without),
        ("sitecheck/registry.py", moved),          # 여기서 q01 이 채워진다
        ("sitecheck/registry.py", registry),       # 여기서 다시 깨진다
    ])

    commits = queue_history.call_commits(git_dir)
    assert [n for n, _ in commits] == [1, 2, 3]

    result = queue_history.grade_chain(TASK, git_dir)
    assert result["snapshots"] == 3
    assert "q01" in result["ever_met"]
    assert [r["item"] for r in result["regressions"]] == ["q01"]


def test_next_md_is_part_of_the_start_state_before_the_baseline(tmp_path):
    """`NEXT.md` 를 스냅숏 훅보다 먼저 만든다.

    스냅숏 저장소는 세션이 시작하기 전 상태를 `baseline` 커밋 하나로 찍어
    둔다. 그 뒤에 만들면 세션이 만든 것처럼 첫 호출의 변경에 들어간다.
    """
    work = tmp_path / "work"
    tpl.build(TASK, work)
    git_dir = tmp_path / "snap.git"
    queue_hook.prepare(work, TASK)
    snapshot.install(work, git_dir)
    listed = subprocess.run(
        ["git", f"--git-dir={git_dir}", "ls-tree", "-r", "--name-only", "HEAD"],
        capture_output=True, text=True, encoding="utf-8", check=False)
    assert "NEXT.md" in listed.stdout.split()
    assert ".casa-queue.json" not in listed.stdout.split()


# --------------------------- 측정 장치가 저장소 안에서 보이지 않는가
#
# `docs/QUEUE_TASK_DEFECTS.md` 7절. 2026-08-28 전에는 설정 파일이 작업 디렉토리
# 안에 있었다 — 세션이 저장소를 훑으면 보이고, 어느 항목 목록으로 채점되는지를
# 알려 준다. `pilot/cut_hook.py` 가 같은 이유로 그 위 디렉토리에 둔다.


def test_the_queue_config_sits_outside_the_working_directory(tmp_path):
    work = tmp_path / "work"
    tpl.build(TASK, work)
    queue_hook.prepare(work, TASK)
    assert not (work / queue_hook.CONFIG_NAME).exists()
    assert (tmp_path / queue_hook.CONFIG_NAME).is_file()


def test_the_hook_still_finds_the_config_from_the_working_directory(tmp_path):
    work = tmp_path / "work"
    tpl.build(TASK, work)
    queue_hook.prepare(work, TASK)
    assert queue_hook.load_task(work) == TASK
    assert queue_hook.refresh(work) is not None


def test_nothing_of_ours_is_left_in_the_repository(tmp_path):
    """세션이 `ls` 를 해도 우리 설정 파일이 안 보여야 한다."""
    work = tmp_path / "work"
    tpl.build(TASK, work)
    queue_hook.prepare(work, TASK)
    assert [p.name for p in work.iterdir() if p.name.startswith(".casa")] == []


# ----------------------------- 세션이 어떻게 끝났는지를 기록에 적는가
#
# `docs/QUEUE_TASK_DEFECTS.md` 3-3. 판정 함수는 있었는데 부르는 곳이 시험뿐이었고,
# 받는 열쇠 이름도 러너가 적는 이름과 달랐다.


def test_the_runner_writes_the_technical_outcome():
    row = {"cut": True, "timed_out": False,
           "audit": {"metrics": {"n_tool_calls": 10, "tool_error_rate": 0.0}}}
    assert run_chain.technical_outcome(row) == "하네스가 끊음"
    assert run_chain.technical_outcome(
        {"cut": False, "timed_out": True}) == "제한 시간 도달"


def test_relevant_files_includes_the_repository_documents():
    """`coverage` 는 이 목록의 파일 중 몇을 읽었는지다.

    큐 항목의 관련 파일만 넣으면 `README.md`·`docs/plan.md`·`RULES.md` 를
    읽었는지가 그 값에 들어가지 않는다.
    """
    listed = (qt.task_dir(TASK) / "relevant_files.txt").read_text(
        encoding="utf-8").split()
    for doc in ("README.md", "RULES.md", "docs/plan.md", "CHANGELOG.md",
                "tests/test_visible.py"):
        assert doc in listed, doc


def test_the_history_refuses_a_directory_with_no_call_snapshots(tmp_path):
    """`docs/QUEUE_TASK_DEFECTS.md` 6절 — 사촌 파일에 같은 결함이 남아 있었다.

    `pilot/queue_observe.py` 는 2026-08-28에 고쳤는데 `pilot/queue_history.py`
    는 그대로여서, 사슬 디렉토리 위를 주면 `스냅숏 0개` 를 찍고 종료 코드 0으로
    끝났다.
    """
    empty = tmp_path / "빈저장소.git"
    subprocess.run(["git", "init", "--bare", str(empty)],
                   capture_output=True, check=True)
    with pytest.raises(ValueError, match="chain-01.git"):
        queue_history.grade_chain(TASK, empty)


def test_the_hook_finds_the_config_from_a_subdirectory(tmp_path):
    """훅이 작업 디렉토리 아래에서 불려도 설정을 찾아야 한다.

    못 찾으면 `NEXT.md` 가 영영 다음 항목을 안 보여 주는데, 훅은 아무 표시도
    남기지 않고 0으로 끝난다.
    """
    work = tmp_path / "work"
    tpl.build(TASK, work)
    queue_hook.prepare(work, TASK)
    assert queue_hook.find_workdir(work) == work.resolve()
    assert queue_hook.find_workdir(work / "sitecheck" / "checks") == work.resolve()
    assert queue_hook.find_workdir(tmp_path / "다른곳") is None
