"""세션 종료 시 인계 검사 테스트 (`harness/handoff_check.py`).

**문서에 규약을 적는 것과 종료 직전에 말해 주는 것은 다르다.** `CLAUDE.md`가
"작업 상태가 바뀌면 같은 커밋에서 STATUS.md를 갱신한다"고 적어 두었는데도
수집 배치 일곱 세션 분량이 3주 동안 기록되지 않았다. 이 훅은 그 규약을
종료 직전에 기계로 확인한다.

pre-commit 훅과 보는 것이 다르다. 그쪽은 **커밋마다** `STATUS.md`가 같이
들어갔는지 보고, 이쪽은 **세션이 끝나는 시점에** 다음 세션이 이어받을 것이
적혀 있는지 본다. 커밋을 안 하고 끝내는 세션은 pre-commit 훅에 안 걸린다.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1] / "harness"
CHECK = HARNESS / "handoff_check.py"


def _load():
    spec = importlib.util.spec_from_file_location("casa_handoff_check", CHECK)
    module = importlib.util.module_from_spec(spec)
    sys.modules["casa_handoff_check"] = module
    spec.loader.exec_module(module)
    return module


check = _load()


def call(name, **payload):
    return {"name": name, "input": payload}


def transcript(tmp_path, calls):
    """훅이 실제로 읽는 모양 그대로 기록 파일을 만든다."""
    path = tmp_path / "transcript.jsonl"
    rows = []
    for one in calls:
        rows.append(json.dumps({
            "type": "assistant",
            "message": {"content": [{"type": "tool_use", "name": one["name"],
                                     "input": one["input"]}]},
        }, ensure_ascii=False))
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return path


# ------------------------------------------- 무엇을 인계 대상으로 보는가

def test_editing_code_without_touching_the_handoff_is_flagged():
    calls = [call("Edit", file_path="src/casa/metrics.py")]
    assert check.changed_files(calls) is True
    assert check.wrote_handoff(calls) is False


def test_editing_code_and_the_handoff_is_not_flagged():
    calls = [call("Edit", file_path="src/casa/metrics.py"),
             call("Edit", file_path="STATUS.md")]
    assert check.wrote_handoff(calls) is True


def test_reading_files_is_not_a_change():
    """읽기만 한 세션에는 인계를 요구하지 않는다."""
    calls = [call("Read", file_path="src/casa/metrics.py"),
             call("Bash", command="git log --oneline -5")]
    assert check.changed_files(calls) is False


def test_touching_only_the_handoff_does_not_require_a_handoff():
    calls = [call("Edit", file_path="STATUS.md")]
    assert check.changed_files(calls) is False


def test_temporary_files_do_not_require_a_handoff():
    calls = [call("Write", file_path="/tmp/scratch.py"),
             call("Write", file_path=".casa/reports/x.json")]
    assert check.changed_files(calls) is False


def test_a_windows_style_path_is_recognized():
    calls = [call("Edit", file_path=r"src\casa\metrics.py")]
    assert check.changed_files(calls) is True


# ------------------------------------------------- 기록을 읽는 방법

def test_the_transcript_reader_skips_lines_it_cannot_parse(tmp_path):
    """기록 형식은 비공개이고 판마다 다르다. 모르는 줄에서 죽으면 훅이
    세션을 막는다."""
    path = tmp_path / "t.jsonl"
    path.write_text(
        "이건 JSON이 아니다\n"
        + json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Edit",
             "input": {"file_path": "a.py"}}]}}, ensure_ascii=False)
        + "\n{\"message\": null}\n",
        encoding="utf-8")
    calls = check.read_calls(path)
    assert len(calls) == 1
    assert calls[0]["name"] == "Edit"


def test_a_missing_transcript_yields_nothing(tmp_path):
    assert check.read_calls(tmp_path / "없는파일.jsonl") == []


# ------------------------------------- 훅을 실제로 실행했을 때의 동작

def _clear(session_id):
    """앞 실행이 남긴 마커를 지운다.

    훅은 세션당 한 번만 막고 그것을 마커 파일로 기억한다. 지우지 않으면
    **테스트가 앞 실행이 남긴 상태에 의존하게 되어**, 따로 돌리면 통과하고
    전체를 돌리면 실패한다. 실제로 그렇게 됐다.
    """
    marker = check._marker(session_id)
    if marker.exists():
        marker.unlink()


def _run(payload):
    _clear(str(payload.get("session_id", "")))
    return subprocess.run([sys.executable, str(CHECK)],
                          input=json.dumps(payload, ensure_ascii=False),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=60)


def _run_again(payload):
    """마커를 지우지 않고 다시 부른다 — 두 번째 호출을 보는 검사용."""
    return subprocess.run([sys.executable, str(CHECK)],
                          input=json.dumps(payload, ensure_ascii=False),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=60)


def test_the_hook_blocks_once_when_the_handoff_is_missing(tmp_path):
    path = transcript(tmp_path, [call("Edit", file_path="src/casa/metrics.py")])
    done = _run({"transcript_path": str(path), "session_id": "t-block"})
    assert done.returncode == 2, done.stdout + done.stderr
    assert "STATUS.md" in done.stderr


def test_the_hook_blocks_only_once_per_session(tmp_path):
    path = transcript(tmp_path, [call("Edit", file_path="src/casa/metrics.py")])
    payload = {"transcript_path": str(path), "session_id": "t-once"}
    assert _run(payload).returncode == 2
    assert _run_again(payload).returncode == 0, "두 번 막으면 세션이 끝나지 못한다"


def test_the_hook_lets_a_session_that_wrote_the_handoff_finish(tmp_path):
    path = transcript(tmp_path, [call("Edit", file_path="src/casa/metrics.py"),
                                 call("Write", file_path="STATUS.md")])
    done = _run({"transcript_path": str(path), "session_id": "t-ok"})
    assert done.returncode == 0, done.stdout + done.stderr


def test_the_hook_does_not_block_a_session_that_changed_nothing(tmp_path):
    path = transcript(tmp_path, [call("Read", file_path="README.md")])
    assert _run({"transcript_path": str(path),
                 "session_id": "t-readonly"}).returncode == 0


def test_the_hook_stands_down_when_it_already_caused_a_continue(tmp_path):
    """`stop_hook_active`가 참이면 이 훅 때문에 이미 한 번 이어진 것이다."""
    path = transcript(tmp_path, [call("Edit", file_path="a.py")])
    done = _run({"transcript_path": str(path), "session_id": "t-active",
                 "stop_hook_active": True})
    assert done.returncode == 0


def test_a_payload_with_no_transcript_is_ignored():
    assert _run({"session_id": "t-empty"}).returncode == 0


# ------------------------------------------------- 배선되어 있는가

def test_the_hook_is_wired_as_a_stop_hook():
    """훅을 만들고 배선을 잊으면 아무 일도 일어나지 않는다."""
    settings = json.loads(
        (Path(__file__).resolve().parents[1] / ".claude" / "settings.json")
        .read_text(encoding="utf-8"))
    commands = [h.get("command", "")
                for entry in settings.get("hooks", {}).get("Stop", [])
                for h in entry.get("hooks", [])]
    assert any("handoff_check" in command for command in commands), commands
