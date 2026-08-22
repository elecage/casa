"""초반에 코드를 안 연 세션을 끊는 훅 테스트 (`pilot/cut_hook.py`).

이 파일이 못 박는 것 다섯.

1. **판정은 정해진 호출까지만 본다.** 그 뒤로 다시 재면 끊는 자리가 신호가
   아니라 세션의 길이에 좌우된다.
2. **설정이 세션의 작업 트리 밖에 있다.** 세션이 읽으면 그것을 보고 행동을
   바꾸고, 그러면 재려던 것이 사라진다.
3. **예산 훅을 덮지 않는다.** 순서가 뒤집히면 끊는 장치가 조용히 사라지고
   두 조건이 같아진 채로 배치가 돈다.
4. **끊지 않기로 한 실행에서는 아무것도 배선하지 않는다.**
5. **연속으로 끊는 횟수에 상한이 있고, 러너가 세션마다 그 횟수를 새로 써
   준다.** 한 번만 써 두면 훅은 첫 세션의 값을 계속 보고 상한이 있으나 마나
   해진다.
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
    assert cut.load_config(work / "opsbox")["at"] == 10


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


def test_all_three_hooks_survive_the_install_order(tmp_path):
    """예산·끊기·스냅숏을 러너가 쓰는 순서로 걸면 셋 다 남는가.

    앞의 테스트는 예산과 끊기 둘만 본다. 스냅숏 훅이 마지막에 걸리므로,
    그것이 `settings.json` 을 통째로 쓰면 앞의 둘이 조용히 사라진다.
    이 프로젝트에서 훅 배선이 조용히 사라진 일이 두 번 있었다.
    """
    snapshot = _load("casa_cut_snapshot", PILOT / "snapshot.py")
    work = tmp_path / "out" / "chain-01"
    work.mkdir(parents=True)

    budget.install(work, 100, 5)
    cut.install(work, at=10, max_streak=2)
    snapshot.install(work, tmp_path / "snap" / "chain-01.git")

    settings = json.loads(
        (work / ".claude" / "settings.json").read_text(encoding="utf-8"))
    hooks = settings["hooks"]
    before = [h["command"] for entry in hooks["PreToolUse"]
              for h in entry["hooks"]]
    after = [h["command"] for entry in hooks["PostToolUse"]
             for h in entry["hooks"]]

    assert any("chain_budget.py" in c for c in before)
    assert any("cut_hook.py" in c for c in before)
    assert any("snapshot.py" in c for c in after)
    # 끊는 훅은 예산 훅 **뒤에** 있어야 한다.
    assert ([i for i, c in enumerate(before) if "cut_hook.py" in c][0]
            > [i for i, c in enumerate(before) if "chain_budget.py" in c][0])


# ------------------------------- 연속으로 끊는 횟수에 상한을 둔다

def test_the_cap_stops_cutting_once_the_streak_is_reached():
    """상한에 닿으면 신호가 켜져도 안 끊는다.

    상한이 없으면 사슬이 열 호출짜리 토막을 계속 만들면서 호출 총량만
    태우고, 그 사슬은 끊기의 손익이 아니라 우리가 사슬을 굶긴 것을
    보여 준다.
    """
    calls = _calls(*["docs/ingest.md"] * 10)
    assert cut.should_cut({"at": 10, "streak": 1, "max_streak": 2}, calls)
    assert not cut.should_cut({"at": 10, "streak": 2, "max_streak": 2}, calls)
    assert not cut.should_cut({"at": 10, "streak": 5, "max_streak": 2}, calls)


def test_no_cap_means_always_cutting_on_the_signal():
    calls = _calls(*["docs/ingest.md"] * 10)
    assert cut.should_cut({"at": 10, "streak": 9, "max_streak": 0}, calls)


def test_the_cap_does_not_cut_a_session_that_opened_code():
    """상한이 남아 있어도 신호가 안 켜지면 안 끊는다."""
    calls = _calls(*["docs/a.md"] * 9 + ["core/months.py"])
    assert not cut.should_cut({"at": 10, "streak": 0, "max_streak": 2}, calls)


def test_the_hook_honours_the_cap_end_to_end(tmp_path):
    work = tmp_path / "chain-01"
    work.mkdir()
    cut.install(work, at=10, streak=2, max_streak=2)
    done = _run_hook(work, _transcript(tmp_path / "t.jsonl",
                                       ["docs/a.md"] * 10))
    assert done.returncode == 0, done.stderr


def test_a_cut_session_is_marked_so_the_runner_can_count_it(tmp_path):
    """러너는 이름이 아니라 개수로 센다 — 세션 식별자가 없을 때가 있다."""
    work = tmp_path / "chain-01"
    work.mkdir()
    cut.install(work, at=10, max_streak=2)
    assert cut.cut_marks(work.parent) == 0

    done = _run_hook(work, _transcript(tmp_path / "t.jsonl",
                                       ["docs/a.md"] * 10))
    assert done.returncode == 2
    assert cut.cut_marks(work.parent) == 1

    # 같은 세션이 호출을 더 해도 한 번만 세어진다.
    _run_hook(work, _transcript(tmp_path / "t.jsonl", ["docs/a.md"] * 12))
    assert cut.cut_marks(work.parent) == 1

    # 다른 세션이 끊기면 하나 더 센다.
    _run_hook(work, _transcript(tmp_path / "u.jsonl", ["docs/a.md"] * 10))
    assert cut.cut_marks(work.parent) == 2


def test_a_session_that_was_let_through_is_not_marked(tmp_path):
    work = tmp_path / "chain-01"
    work.mkdir()
    cut.install(work, at=10, max_streak=2)
    _run_hook(work, _transcript(
        tmp_path / "t.jsonl", ["docs/a.md"] * 9 + ["core/months.py"]))
    assert cut.cut_marks(work.parent) == 0


def test_the_runner_rewrites_the_streak_before_every_session():
    """상한이 들으려면 러너가 세션마다 연속 횟수를 새로 써 줘야 한다.

    한 번만 써 두면 훅은 첫 세션의 값을 계속 보고, 상한이 있으나 마나 해진다.
    """
    body = (PILOT / "run_chain.py").read_text(encoding="utf-8")
    inside = body[body.index("    while True:"):]
    assert "cut_hook.install(workdir, cut_at, streak=cut_streak" in inside
    assert "cut_hook.cut_marks(workdir.parent) > marks_before" in inside
