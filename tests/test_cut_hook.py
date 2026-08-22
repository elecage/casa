"""초반에 코드를 안 연 세션을 끊는 훅 테스트 (`pilot/cut_hook.py`).

이 파일이 못 박는 것 넷.

1. **판정은 정해진 호출까지만 본다.** 그 뒤로 다시 재면 끊는 자리가 신호가
   아니라 세션의 길이에 좌우된다.
2. **설정이 세션의 작업 트리 밖에 있다.** 세션이 읽으면 그것을 보고 행동을
   바꾸고, 그러면 재려던 것이 사라진다.
3. **예산 훅을 덮지 않는다.** 순서가 뒤집히면 끊는 장치가 조용히 사라지고
   두 조건이 같아진 채로 배치가 돈다.
4. **끊지 않기로 한 실행에서는 아무것도 배선하지 않는다.**
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "pilot"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


cut = _load("casa_cut_hook", PILOT / "cut_hook.py")
budget = _load("casa_cut_budget", PILOT / "chain_budget.py")


def _calls(*paths: str) -> list[dict]:
    return [{"name": "Read", "input": {"file_path": p}} for p in paths]


# --------------------------------------------------- 무엇을 보고 끊는가

def test_a_session_that_never_opened_code_is_cut():
    assert cut.decide(_calls(*["docs/ingest.md"] * 10), at=10) is True


def test_a_session_that_opened_code_is_left_alone():
    calls = _calls(*(["docs/ingest.md"] * 9 + ["opsbox/ingest/bd.py"]))
    assert cut.decide(calls, at=10) is False


def test_nothing_is_decided_before_the_window_is_full():
    """열 호출이 되기 전에는 판정하지 않는다. 다섯 호출째에 끊으면 그것은
    다른 실험이다."""
    assert cut.decide(_calls(*["docs/a.md"] * 9), at=10) is False


def test_the_window_is_not_re_judged_later():
    """**정해진 호출까지만 본다.** 그 뒤로 다시 재면 끊는 자리가 신호가 아니라
    그 세션의 길이에 좌우된다 — 코드를 늦게 연 세션이 계속 살아남고, 일찍
    열었다가 문서로 돌아간 세션이 나중에 끊긴다.
    """
    late = _calls(*(["docs/a.md"] * 10 + ["opsbox/ingest/bd.py"] * 20))
    assert cut.decide(late, at=10) is True, "열 호출째 판정이 뒤집히면 안 된다"

    early = _calls(*(["opsbox/ingest/bd.py"] + ["docs/a.md"] * 30))
    assert cut.decide(early, at=10) is False


def test_a_shell_command_that_names_a_code_file_counts():
    """읽기 도구로만 여는 것이 아니다."""
    calls = [{"name": "Bash", "input": {"command": "sed -n 1,20p opsbox/x.py"}}]
    calls += _calls(*["docs/a.md"] * 9)
    assert cut.decide(calls, at=10) is False


def test_zero_means_do_not_cut():
    assert cut.decide(_calls(*["docs/a.md"] * 30), at=0) is False


# ------------------------------------- 설정은 세션의 작업 트리 밖에 있다

def test_the_config_is_kept_out_of_the_session_tree(tmp_path):
    work = tmp_path / "chain-01"
    work.mkdir()
    cut.install(work, at=10)
    assert not (work / cut.CONFIG_NAME).exists()
    assert (tmp_path / cut.CONFIG_NAME).is_file()


def test_the_hook_finds_the_config_from_inside_the_workdir(tmp_path):
    work = tmp_path / "chain-01"
    (work / "opsbox").mkdir(parents=True)
    cut.install(work, at=10)
    assert cut.load_config(work / "opsbox") == {"at": 10}


# ------------------------------------------- 예산 훅을 덮지 않는다

def test_the_cut_hook_does_not_replace_the_budget_hook(tmp_path):
    """**순서가 뒤집히면 끊는 장치가 조용히 사라진다.** 예산 훅이 PreToolUse
    목록을 통째로 쓰므로 이 훅이 나중에 배선돼야 하고, 그때 예산 훅을 밀어내면
    안 된다."""
    work = tmp_path / "chain-01"
    work.mkdir()
    budget.install(work, budget=30)
    cut.install(work, at=10)

    settings = json.loads((work / ".claude" / "settings.json").read_text(
        encoding="utf-8"))
    commands = [h["command"] for entry in settings["hooks"]["PreToolUse"]
                for h in entry["hooks"]]
    assert any("chain_budget.py" in c for c in commands), commands
    assert any("cut_hook.py" in c for c in commands), commands


def test_installing_twice_does_not_double_the_hook(tmp_path):
    work = tmp_path / "chain-01"
    work.mkdir()
    cut.install(work, at=10)
    cut.install(work, at=10)
    settings = json.loads((work / ".claude" / "settings.json").read_text(
        encoding="utf-8"))
    commands = [h["command"] for entry in settings["hooks"]["PreToolUse"]
                for h in entry["hooks"]]
    assert sum("cut_hook.py" in c for c in commands) == 1


def test_not_cutting_wires_nothing(tmp_path):
    work = tmp_path / "chain-01"
    work.mkdir()
    cut.install(work, at=0)
    assert not (work / ".claude").exists()
    assert not (tmp_path / cut.CONFIG_NAME).exists()


def test_the_runner_wires_the_cut_hook_after_the_budget_hook():
    source = (PILOT / "run_chain.py").read_text(encoding="utf-8")
    assert source.index("install_budget(workdir") < source.index(
        "cut_hook.install(workdir")


# ------------------------------------------------- 훅을 프로세스로 부른다

def _run_hook(work: Path, transcript: Path):
    payload = json.dumps({"cwd": str(work), "transcript_path": str(transcript)})
    return subprocess.run([sys.executable, str(PILOT / "cut_hook.py")],
                          input=payload, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=60)


def _transcript(path: Path, paths: list[str]) -> Path:
    lines = [json.dumps({
        "type": "assistant",
        "message": {"content": [{"type": "tool_use", "name": "Read",
                                 "input": {"file_path": p}}]}})
        for p in paths]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_the_hook_blocks_a_session_that_never_opened_code(tmp_path):
    work = tmp_path / "chain-01"
    work.mkdir()
    cut.install(work, at=10)
    done = _run_hook(work, _transcript(tmp_path / "t.jsonl",
                                       ["docs/a.md"] * 10))
    assert done.returncode == 2
    assert "끝낸다" in done.stderr


def test_the_hook_lets_a_session_that_opened_code_through(tmp_path):
    work = tmp_path / "chain-01"
    work.mkdir()
    cut.install(work, at=10)
    done = _run_hook(work, _transcript(
        tmp_path / "t.jsonl", ["docs/a.md"] * 9 + ["opsbox/ingest/bd.py"]))
    assert done.returncode == 0


def test_the_hook_does_nothing_without_a_config(tmp_path):
    """끊지 않는 조건에서는 이 훅이 배선되지 않지만, 배선된 채 설정만 없어도
    세션을 막으면 안 된다."""
    work = tmp_path / "chain-01"
    work.mkdir()
    done = _run_hook(work, _transcript(tmp_path / "t.jsonl",
                                       ["docs/a.md"] * 30))
    assert done.returncode == 0
