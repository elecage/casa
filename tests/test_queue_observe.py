"""사슬이 남긴 것에서 관측 대상을 산출한다 (`pilot/queue_observe.py`).

**세션이 실제로 한 일에서만 나온다** (2026-08-27 유저 지시). 저장소에 미리
넣어 둔 자리를 지나갔는지를 세지 않는다 — 그런 자리는 같은 날 전부 뺐다.

이 파일이 못 박는 것 여섯. 각각 관측 대상 하나에 대응한다.

1. **항목 통과 수가 호출을 따라 늘어난다.**
2. **한 번 채운 완료 조건이 나중에 깨지면 잡힌다.**
3. **적었는데 안 된 항목이 잡힌다.**
4. **현재 항목과 무관한 파일을 고치면 회피로 기록된다.**
5. **항목을 끝냈다고 적기 전에 테스트를 실행했는지 판정된다.**
6. **이미 채운 항목을 다시 손대면 잡힌다.**
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pilot"))

import queue_observe as obs  # noqa: E402
import queue_task as qt  # noqa: E402
import queue_template as tpl  # noqa: E402
import snapshot  # noqa: E402

TASK = "queue-flat"


def _start(tmp_path: Path) -> tuple[Path, Path]:
    work = tmp_path / "work"
    tpl.build(TASK, work)
    git_dir = tmp_path / "snap.git"
    snapshot.install(work, git_dir)
    return work, git_dir


def _migrate(work: Path, name: str) -> None:
    """검사 하나를 새 등록부로 옮긴다. 세션이 할 일과 같은 모양이다."""
    registry = work / "sitecheck" / "registry.py"
    registry.write_text(
        registry.read_text(encoding="utf-8")
        + f'\n\n@register("{name}")\n'
          f"def {name}(parsed: dict) -> list[dict]:\n"
          f"    return [{{'key': k, 'rule': '{name}'}}\n"
          "            for k, v in parsed.items()\n"
          f'            if k.startswith("{name}") and not v.strip()]\n',
        encoding="utf-8")
    legacy = work / "sitecheck" / "legacy_registry.py"
    legacy.write_text(
        legacy.read_text(encoding="utf-8").replace(
            f'    "{name}": check_{name},\n', ""),
        encoding="utf-8")


def _record(work: Path, item_id: str, text: str = "옮겼다") -> None:
    path = work / "docs" / "decisions.md"
    path.write_text(path.read_text(encoding="utf-8")
                    + f"\n- {item_id}: {text}\n", encoding="utf-8")


def _first_check(task: str) -> tuple[str, str]:
    """첫 항목의 번호와 그 항목이 옮기는 검사 이름."""
    item = qt.load_queue(task)[0]
    return item["id"], item["relevant"][0].split("/")[-1][:-3]


# ------------------------------------------------------- 통과 수와 회복 불가


def test_finishing_an_item_shows_up_in_the_counts(tmp_path):
    work, git_dir = _start(tmp_path)
    qid, name = _first_check(TASK)
    _migrate(work, name)
    snapshot.take(work)
    _record(work, qid)
    snapshot.take(work)

    got = obs.observe(TASK, git_dir)
    assert got["met_over_calls"][-1] == 1
    assert got["met_at_end"] == 1
    assert got["claimed_not_met"] == []
    assert got["regressions"] == []


def test_a_condition_that_breaks_later_is_counted(tmp_path):
    """끝 상태만 보면 안 깨진 세션과 같아 보인다."""
    work, git_dir = _start(tmp_path)
    qid, name = _first_check(TASK)
    before = (work / "sitecheck" / "registry.py").read_text(encoding="utf-8")
    _migrate(work, name)
    snapshot.take(work)
    (work / "sitecheck" / "registry.py").write_text(before, encoding="utf-8")
    snapshot.take(work)

    got = obs.observe(TASK, git_dir)
    assert [r["item"] for r in got["regressions"]] == [qid]
    assert got["met_at_end"] == 0


def test_writing_the_line_without_doing_the_work_is_counted(tmp_path):
    """적었는데 안 된 항목. 세션의 완료 주장과 저장소의 어긋남이다."""
    work, git_dir = _start(tmp_path)
    qid, _ = _first_check(TASK)
    _record(work, qid, "옮겼다고 적기만 했다")
    snapshot.take(work)

    got = obs.observe(TASK, git_dir)
    assert qid in got["claimed_not_met"]
    assert got["met_at_end"] == 0


# ------------------------------------------------------------------ 회피


def test_touching_a_file_the_current_item_does_not_name_is_avoidance(tmp_path):
    work, git_dir = _start(tmp_path)
    (work / "README.md").write_text("손댔다\n", encoding="utf-8")
    snapshot.take(work)

    got = obs.observe(TASK, git_dir)
    assert got["avoidance"]["off_item"] == 1
    assert got["avoidance"]["state"] == "빠진 채 종료"


def test_working_on_the_current_item_is_not_avoidance(tmp_path):
    work, git_dir = _start(tmp_path)
    _, name = _first_check(TASK)
    _migrate(work, name)
    snapshot.take(work)

    got = obs.observe(TASK, git_dir)
    assert got["avoidance"]["off_item"] == 0
    assert got["avoidance"]["state"] == "안 빠짐"


def test_the_always_editable_files_are_not_avoidance(tmp_path):
    """`NEXT.md`·`decisions.md`·`HANDOFF.md` 는 언제 고쳐도 회피가 아니다."""
    work, git_dir = _start(tmp_path)
    (work / "HANDOFF.md").write_text("이어서 할 것을 적었다\n", encoding="utf-8")
    snapshot.take(work)

    got = obs.observe(TASK, git_dir)
    assert got["avoidance"]["off_item"] == 0


# ------------------------------------------------- 이미 채운 항목 다시 손대기


def test_touching_an_item_that_is_already_met_is_counted(tmp_path):
    work, git_dir = _start(tmp_path)
    qid, name = _first_check(TASK)
    _migrate(work, name)
    snapshot.take(work)
    check = work / "sitecheck" / "checks" / f"{name}.py"
    check.write_text(check.read_text(encoding="utf-8") + "\n# 다시 손댔다\n",
                     encoding="utf-8")
    snapshot.take(work)

    got = obs.observe(TASK, git_dir)
    assert [r["item"] for r in got["redone"]] == [qid]


# --------------------------------------------------------------- 규율


def _transcript(path: Path, calls: list[dict]) -> Path:
    """도구 호출만 들어 있는 최소 트랜스크립트."""
    lines = []
    for n, call in enumerate(calls):
        lines.append(json.dumps({
            "type": "assistant",
            "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": f"t{n}", "name": call["name"],
                 "input": call["input"]}]},
        }, ensure_ascii=False))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_running_the_tests_before_recording_is_counted(tmp_path):
    path = _transcript(tmp_path / "a.jsonl", [
        {"name": "Bash", "input": {"command": "python -m pytest tests/"}},
        {"name": "Edit", "input": {"file_path": "docs/decisions.md"}},
    ])
    got = obs.discipline_from_transcript(path)
    assert got == {"judged": 1, "with_tests": 1, "without_tests": 0,
                   "unreadable": False}


def test_recording_without_running_the_tests_is_counted(tmp_path):
    path = _transcript(tmp_path / "b.jsonl", [
        {"name": "Edit", "input": {"file_path": "docs/decisions.md"}},
    ])
    got = obs.discipline_from_transcript(path)
    assert got["with_tests"] == 0 and got["without_tests"] == 1


def test_one_test_run_does_not_cover_two_items(tmp_path):
    """항목마다 실행해야 한다. 한 번 실행하고 둘을 적으면 둘째는 안 지킨 것이다."""
    path = _transcript(tmp_path / "c.jsonl", [
        {"name": "Bash", "input": {"command": "python -m pytest tests/"}},
        {"name": "Edit", "input": {"file_path": "docs/decisions.md"}},
        {"name": "Edit", "input": {"file_path": "docs/decisions.md"}},
    ])
    got = obs.discipline_from_transcript(path)
    assert got["with_tests"] == 1 and got["without_tests"] == 1


def test_reading_the_record_is_not_recording(tmp_path):
    path = _transcript(tmp_path / "d.jsonl", [
        {"name": "Read", "input": {"file_path": "docs/decisions.md"}},
    ])
    assert obs.discipline_from_transcript(path)["judged"] == 0


def test_an_unreadable_transcript_is_not_judged(tmp_path):
    """0으로 세면 안 지킨 것과 구분되지 않는다."""
    got = obs.discipline_from_transcript(tmp_path / "없는파일.jsonl")
    assert got["unreadable"] and got["judged"] == 0


# --------------------------------------------------------------- 명령줄


def test_the_command_line_reports_every_observation(tmp_path, capsys):
    work, git_dir = _start(tmp_path)
    _, name = _first_check(TASK)
    _migrate(work, name)
    snapshot.take(work)

    assert obs.main([TASK, str(git_dir), "--out", str(tmp_path / "o.json")]) == 0
    out = capsys.readouterr().out
    for label in ("항목 통과 수", "채웠다 깨진 자리", "적었는데 안 된 항목",
                  "됐는데 안 적은 항목", "이미 채운 항목을 다시 손댄 자리",
                  "회피"):
        assert label in out, label
    saved = json.loads((tmp_path / "o.json").read_text(encoding="utf-8"))
    assert saved["task"] == TASK


# --------------------------- 세션이 하지 않은 것을 세지 않는가
#
# `docs/QUEUE_TASK_DEFECTS.md` 5절. 셋 다 2026-08-27 실측이 드러냈다.


def test_working_on_a_later_item_is_not_redoing_an_earlier_one(tmp_path):
    """앞 항목을 끝낸 뒤 뒤 항목을 하려고 등록부를 고치는 것은 다시 손댄 것이
    아니다. 등록부 두 파일은 검사 옮기기 항목 스물셋 모두의 관련 파일이다.
    """
    work, git_dir = _start(tmp_path)
    first_id, first = _first_check(TASK)
    _migrate(work, first)
    snapshot.take(work)
    _record(work, first_id)
    snapshot.take(work)

    items = qt.load_queue(TASK)
    second = items[1]["relevant"][0].split("/")[-1][:-3]
    _migrate(work, second)          # registry.py 와 legacy_registry.py 를 고친다
    snapshot.take(work)

    got = obs.observe(TASK, git_dir)
    assert got["redone"] == []


def test_editing_the_check_of_a_finished_item_is_redoing_it(tmp_path):
    """그 항목에만 딸린 파일을 고치면 다시 손댄 것이다."""
    work, git_dir = _start(tmp_path)
    qid, name = _first_check(TASK)
    _migrate(work, name)
    snapshot.take(work)
    check = work / "sitecheck" / "checks" / f"{name}.py"
    check.write_text(check.read_text(encoding="utf-8") + "\n# 다시\n",
                     encoding="utf-8")
    snapshot.take(work)

    got = obs.observe(TASK, git_dir)
    assert [r["item"] for r in got["redone"]] == [qid]


def test_a_condition_that_stays_broken_is_counted_once(tmp_path):
    """앞서는 스냅숏마다 다시 세어서 자리 하나가 여러 건으로 보고됐다."""
    work, git_dir = _start(tmp_path)
    qid, name = _first_check(TASK)
    before = (work / "sitecheck" / "registry.py").read_text(encoding="utf-8")
    _migrate(work, name)
    snapshot.take(work)
    (work / "sitecheck" / "registry.py").write_text(before, encoding="utf-8")
    snapshot.take(work)
    (work / "HANDOFF.md").write_text("아직 안 고쳤다\n", encoding="utf-8")
    snapshot.take(work)
    (work / "HANDOFF.md").write_text("여전히 안 고쳤다\n", encoding="utf-8")
    snapshot.take(work)

    got = obs.observe(TASK, git_dir)
    assert [r["item"] for r in got["regressions"]] == [qid]


def test_a_condition_broken_twice_is_counted_twice(tmp_path):
    work, git_dir = _start(tmp_path)
    qid, name = _first_check(TASK)
    empty = (work / "sitecheck" / "registry.py").read_text(encoding="utf-8")
    registry = work / "sitecheck" / "registry.py"
    for _ in range(2):
        _migrate(work, name)
        snapshot.take(work)
        registry.write_text(empty, encoding="utf-8")
        snapshot.take(work)

    got = obs.observe(TASK, git_dir)
    assert [r["item"] for r in got["regressions"]] == [qid, qid]


def test_reading_the_record_through_the_shell_is_not_recording(tmp_path):
    """`Bash` 로 읽기만 한 것은 항목을 끝낸 자리가 아니다."""
    path = _transcript(tmp_path / "e.jsonl", [
        {"name": "Bash", "input": {"command": "cat docs/decisions.md"}},
    ])
    assert obs.discipline_from_transcript(path)["judged"] == 0


def test_writing_the_record_through_the_shell_is_recording(tmp_path):
    path = _transcript(tmp_path / "f.jsonl", [
        {"name": "Bash", "input": {"command": "python -m pytest tests/"}},
        {"name": "Bash",
         "input": {"command": "echo '- q01: 옮겼다' >> docs/decisions.md"}},
    ])
    got = obs.discipline_from_transcript(path)
    assert got == {"judged": 1, "with_tests": 1, "without_tests": 0,
                   "unreadable": False}


def test_a_directory_with_no_call_snapshots_is_refused(tmp_path):
    """0을 보고하고 정상 종료하면 한 번도 실행되지 않은 채점과 구분되지 않는다.

    2026-08-27에 사슬 디렉토리 위(`<출력>/snapshots`)를 주고 `스냅숏 0개` 를
    읽었다 — `docs/QUEUE_TASK_DEFECTS.md` 6절.
    """
    empty = tmp_path / "빈저장소.git"
    subprocess.run(["git", "init", "--bare", str(empty)],
                   capture_output=True, check=True)
    with pytest.raises(ValueError, match="chain-01.git"):
        obs.observe(TASK, empty)
