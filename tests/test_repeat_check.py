"""기존 자료로 같은 분석을 되풀이하는 것을 확인하는 훅 (`harness/repeat_check.py`).

**왜 이 훅이 있나.** 2026-08-23 세션이 하루에 여섯 번 같은 절차를 되풀이했고,
매번 세부 호출이 달라 기존 지표에 검출되지 않았다. 유저가 대화로 지적해야만
드러났다 — "너 지금 똑같은 일을 몇 번째 반복하고 있는 거 아냐."

이 파일이 못 박는 것 다섯.

1. **호출 하나가 아니라 분석 스크립트 실행 횟수를 센다.** 인자가 매번 달라도
   세어진다 — 그것이 검출되지 않던 자리다.
2. **한 스크립트를 서로 다른 인자로 여러 번 실행한 것도 검출된다**, 총 횟수가
   기준에 못 미쳐도.
3. **수집 잠금이 열려 있으면 보지 않는다.** 새 자료를 모으는 중에 분석을
   여러 번 실행하는 것은 정상이다.
4. **차단 메시지가 무엇을 해야 하는지 적는다** — 봉인한 예측을 밝히거나,
   잠금 해제 승인을 요청하거나, 되풀이가 아닌 이유를 적는다.
5. **기록을 못 읽어도 세션을 막지 않는다.**
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness"))

import repeat_check as rc  # noqa: E402


def _bash(command: str) -> dict:
    return {"name": "Bash", "input": {"command": command}}


def _run_call(script: str, args: str = "") -> dict:
    return _bash(f".venv/bin/python pilot/analysis/{script} {args}".strip())


# ------------------------------------------------------- 무엇을 실행으로 세나


def test_an_analysis_script_run_is_counted():
    runs = rc.analysis_runs([_run_call("rework.py", "--arm results/cut/keep")])
    assert runs == [("rework.py", "--arm results/cut/keep")]


def test_a_windows_path_is_counted():
    runs = rc.analysis_runs(
        [_bash(r".venv\Scripts\python.exe pilot\analysis\cut_eval.py --at 20")])
    assert runs == [("cut_eval.py", "--at 20")]


def test_two_runs_in_one_shell_command_are_both_counted():
    runs = rc.analysis_runs(
        [_bash("python pilot/analysis/a.py --x && python pilot/analysis/b.py --y")])
    assert [name for name, _ in runs] == ["a.py", "b.py"]
    assert runs[0][1] == "--x"


def test_other_commands_are_not_counted():
    assert rc.analysis_runs([_bash("python -m pytest"),
                             _bash("git status"),
                             {"name": "Read", "input": {"file_path": "a.py"}}]) == []


def test_a_call_without_a_command_is_skipped():
    assert rc.analysis_runs([{"name": "Bash", "input": {}}, {"name": "Edit"}]) == []


# --------------------------------------------------------------- 판정


def test_many_runs_across_scripts_are_caught():
    """2026-08-23의 모습 — 매번 다른 스크립트라 기존 지표에 안 검출됐다."""
    calls = [_run_call(f"s{i}.py", f"--arm {i}") for i in range(8)]
    found = rc.judge(rc.analysis_runs(calls))
    assert found and found["total"] == 8


def test_one_script_with_many_argument_sets_is_caught_below_the_total():
    calls = [_run_call("rework.py", f"--arm results/{i}") for i in range(4)]
    found = rc.judge(rc.analysis_runs(calls), total=8, variants=4)
    assert found and "rework.py" in found["repeated"]


def test_the_same_arguments_repeated_are_not_a_variant_sweep():
    """같은 명령을 다시 실행하는 것은 이 훅이 보는 것이 아니다."""
    calls = [_run_call("rework.py", "--arm results/x") for _ in range(4)]
    assert rc.judge(rc.analysis_runs(calls), total=8, variants=4) is None


def test_a_few_runs_pass():
    calls = [_run_call("rework.py", "--arm results/x"),
             _run_call("cut_eval.py", "--at 20")]
    assert rc.judge(rc.analysis_runs(calls)) is None


def test_the_message_names_the_three_ways_out():
    found = rc.judge(rc.analysis_runs(
        [_run_call(f"s{i}.py", f"--arm {i}") for i in range(8)]))
    body = rc.build_message(found, {"unlock_requires": "유저 승인"})
    assert "봉인" in body and "유저 승인" in body and "STATUS.md" in body


# ---------------------------------------------------------- 기록 읽기


def _transcript(tmp_path: Path, commands: list[str]) -> Path:
    path = tmp_path / "t.jsonl"
    rows = []
    for command in commands:
        rows.append(json.dumps({"message": {"content": [
            {"type": "tool_use", "name": "Bash", "input": {"command": command}}]}}))
    rows.append("깨진 줄이 하나 있어도 죽으면 안 된다")
    path.write_text("\n".join(rows), encoding="utf-8")
    return path


def test_the_transcript_parser_tolerates_broken_lines(tmp_path):
    path = _transcript(tmp_path, ["python pilot/analysis/rework.py --arm x"])
    assert len(rc.read_calls(path)) == 1


def test_a_missing_transcript_is_not_fatal(tmp_path):
    assert rc.read_calls(tmp_path / "없는파일.jsonl") == []


# ------------------------------------------------------------- 훅으로 실행


def _hook(payload: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "harness" / "repeat_check.py")],
        input=payload, capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
    )


def test_the_hook_blocks_while_the_collection_gate_is_locked(tmp_path, monkeypatch):
    path = _transcript(tmp_path, [f"python pilot/analysis/s{i}.py --arm {i}"
                                  for i in range(8)])
    monkeypatch.setattr(rc, "gate_state", lambda _name: "locked")
    monkeypatch.setattr(rc, "_marker", lambda _sid: tmp_path / "m")
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(
        json.dumps({"transcript_path": str(path)})))
    assert rc.main() == 2


def test_the_hook_does_not_look_while_the_gate_is_open(tmp_path, monkeypatch):
    """새 자료를 모으는 중에 분석을 여러 번 실행하는 것은 정상이다."""
    path = _transcript(tmp_path, [f"python pilot/analysis/s{i}.py --arm {i}"
                                  for i in range(8)])
    monkeypatch.setattr(rc, "gate_state", lambda _name: "open")
    monkeypatch.setattr(rc, "_marker", lambda _sid: tmp_path / "m")
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(
        json.dumps({"transcript_path": str(path)})))
    assert rc.main() == 0


def test_the_hook_blocks_only_once_per_session(tmp_path, monkeypatch):
    path = _transcript(tmp_path, [f"python pilot/analysis/s{i}.py --arm {i}"
                                  for i in range(8)])
    marker = tmp_path / "m"
    monkeypatch.setattr(rc, "gate_state", lambda _name: "locked")
    monkeypatch.setattr(rc, "_marker", lambda _sid: marker)
    payload = json.dumps({"transcript_path": str(path)})
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(payload))
    assert rc.main() == 2
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(payload))
    assert rc.main() == 0


def test_the_hook_does_not_recurse_on_its_own_block():
    assert _hook(json.dumps({"transcript_path": "x", "stop_hook_active": True})
                 ).returncode == 0


def test_the_hook_survives_garbage_input():
    assert _hook("not json at all").returncode == 0
    assert _hook(json.dumps({})).returncode == 0
    assert _hook(json.dumps({"transcript_path": ""})).returncode == 0


# ------------------------------------------------------------- 설정


def test_the_gate_entry_declares_this_check():
    data = json.loads((ROOT / "harness" / "gates.json").read_text(encoding="utf-8"))
    entry = data.get("repeat_check")
    assert isinstance(entry, dict)
    assert entry.get("state") and entry.get("reason")


def test_the_hook_is_registered_in_settings():
    text = (ROOT / ".claude" / "settings.json").read_text(encoding="utf-8")
    assert "repeat_check" in text
