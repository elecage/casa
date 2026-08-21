"""Tests for chain running and the session budget.

Chains break assumptions the single-shot runner could rely on, so these pin
the three that would silently corrupt a chain run:

1. the working directory must be prepared once, at session 1. Preparing it
   again would wipe the previous session's work — and inheriting that work is
   the entire reason the arm exists.
2. transcripts of a chain land in one shared directory, so a session must not
   pick up a transcript an earlier session already claimed.
3. the budget must leave a window before the cap. Writing a handoff note is
   itself a tool call, so a hard stop with no warning makes the handoff — the
   variable being measured — impossible for every session.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pilot"))

import chain_budget  # noqa: E402
import run_chain  # noqa: E402


# ------------------------------------------------------------- the budget


def _transcript(path: Path, n_calls: int) -> Path:
    lines = []
    for i in range(n_calls):
        lines.append(json.dumps({
            "type": "assistant",
            "message": {"content": [
                {"type": "tool_use", "id": f"t{i}", "name": "Bash", "input": {}}]},
        }))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_tool_calls_are_counted_from_the_transcript(tmp_path):
    assert chain_budget.count_tool_calls(_transcript(tmp_path / "t.jsonl", 7)) == 7


def test_counting_ignores_junk_lines(tmp_path):
    path = tmp_path / "t.jsonl"
    _transcript(path, 3)
    path.write_text(path.read_text(encoding="utf-8") + "not json\n{}\n",
                    encoding="utf-8")
    assert chain_budget.count_tool_calls(path) == 3


def test_missing_transcript_counts_as_zero(tmp_path):
    assert chain_budget.count_tool_calls(tmp_path / "nope.jsonl") == 0


def test_budget_warns_before_it_blocks():
    """Without a window, no session could ever write a handoff note."""
    quiet, _ = chain_budget.decide(used=10, budget=60, warn_at=55)
    warn_code, warn_msg = chain_budget.decide(used=57, budget=60, warn_at=55)
    stop_code, stop_msg = chain_budget.decide(used=90, budget=60, warn_at=55)

    assert quiet == 0
    assert warn_code == 0 and "3회 남았다" in warn_msg
    assert stop_code == 2 and "상한" in stop_msg


def test_warning_says_how_many_are_left():
    _, message = chain_budget.decide(used=55, budget=60, warn_at=55)
    assert "55/60" in message and "5회" in message


def test_going_over_the_budget_is_not_blocked():
    """**예산은 가위가 아니라 안전판이다**(2026-08-21 유저 지시).

    예산에서 딱 자르면 세션이 서브시스템 중간에서 끊기고, 어디서 멈췄는지가
    일의 양이 아니라 우리가 넣은 수가 정한 것이 된다. 일의 양은 서브시스템마다
    다르고, 조금 넘겨서 하던 것을 끝내는 것은 실제 작업에서 일어나는 일이다.
    """
    code, message = chain_budget.decide(used=61, budget=60, warn_at=55)
    assert code == 0, "예산을 한 번 넘었다고 막으면 안 된다"
    assert "1회 초과" in message
    assert "90회에서" in message, "어디서 막히는지 알려 줘야 한다"


def test_the_hard_cap_still_blocks():
    """**과하게 넘어가는 것은 막는다.** 넘긴 양이 곧 관측값이지만 무한정은 아니다."""
    below, _ = chain_budget.decide(used=89, budget=60, warn_at=55)
    at_cap, message = chain_budget.decide(used=90, budget=60, warn_at=55)
    assert below == 0
    assert at_cap == 2 and "상한" in message


def test_the_hard_cap_is_half_again_the_budget():
    """예산 30이면 45다. 하던 서브시스템 하나를 끝내기에는 넉넉하고 두셋을
    더 하기에는 모자란다. 작은 예산에서는 최소 10회를 준다."""
    assert chain_budget.hard_cap_for(30) == 45
    assert chain_budget.hard_cap_for(60) == 90
    assert chain_budget.hard_cap_for(12) == 22


def test_the_config_carries_the_hard_cap(tmp_path):
    chain_budget.install(tmp_path, budget=30)
    config = json.loads(
        (tmp_path / ".casa-chain.json").read_text(encoding="utf-8"))
    assert config == {"budget": 30, "warn_at": 25, "hard_cap": 45}


def test_every_session_row_records_the_hard_cap():
    """넘긴 양을 나중에 세려면 예산과 상한이 둘 다 기록에 있어야 한다."""
    source = (ROOT / "pilot" / "run_chain.py").read_text(encoding="utf-8")
    assert '"budget_hard_cap": chain_budget.hard_cap_for(budget),' in source


def test_config_is_read_from_the_workdir(tmp_path):
    (tmp_path / ".casa-chain.json").write_text(
        json.dumps({"budget": 12, "warn_at": 9}), encoding="utf-8")
    assert chain_budget.load_config(tmp_path) == {"budget": 12, "warn_at": 9}


def test_missing_or_broken_config_is_not_fatal(tmp_path):
    assert chain_budget.load_config(tmp_path) == {}
    (tmp_path / ".casa-chain.json").write_text("{broken", encoding="utf-8")
    assert chain_budget.load_config(tmp_path) == {}


# --------------------------------------------------------- wiring the hook


def test_install_budget_writes_config_and_hook(tmp_path):
    run_chain.install_budget(tmp_path, budget=60)
    config = json.loads((tmp_path / ".casa-chain.json").read_text(encoding="utf-8"))
    assert config == {"budget": 60, "warn_at": 55, "hard_cap": 90}

    settings = json.loads(
        (tmp_path / ".claude" / "settings.json").read_text(encoding="utf-8"))
    command = settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    assert "chain_budget.py" in command


def test_hook_is_installed_per_chain_not_globally(tmp_path):
    """A chain run must not leak its budget into the developer's own sessions."""
    run_chain.install_budget(tmp_path, budget=60)
    assert (tmp_path / ".claude" / "settings.json").exists()
    assert not (ROOT / ".casa-chain.json").exists()


# ---------------------------------------------------------- transcript pick


def test_a_transcript_already_claimed_is_not_taken_again(tmp_path, monkeypatch):
    tdir = tmp_path / "project"
    tdir.mkdir()
    first = tdir / "aaa.jsonl"
    first.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(run_chain, "transcript_dir_for", lambda _w: tdir)

    out = tmp_path / "out"
    out.mkdir()
    seen: set[str] = set()
    got = run_chain.collect_transcript(tmp_path, {}, out, "c01s01", seen)
    assert got is not None and "aaa.jsonl" in seen

    # Second session, no new transcript written: must not reuse the first.
    assert run_chain.collect_transcript(tmp_path, {}, out, "c01s02", seen) is None

    second = tdir / "bbb.jsonl"
    second.write_text("{}\n", encoding="utf-8")
    got2 = run_chain.collect_transcript(tmp_path, {}, out, "c01s02", seen)
    assert got2 is not None and got2.name == "transcript-c01s02.jsonl"


def test_session_id_is_preferred_when_present(tmp_path, monkeypatch):
    tdir = tmp_path / "project"
    tdir.mkdir()
    (tdir / "old.jsonl").write_text("{}\n", encoding="utf-8")
    wanted = tdir / "wanted.jsonl"
    wanted.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(run_chain, "transcript_dir_for", lambda _w: tdir)

    out = tmp_path / "out"
    out.mkdir()
    run_chain.collect_transcript(tmp_path, {"session_id": "wanted"}, out,
                                 "c01s01", set())
    assert (out / "transcript-c01s01.jsonl").exists()


# ------------------------------------------------------------- chain roll-up


def _row(score, violations=0, wall=1.0):
    return {"grade": {"milestone_score": score, "violations": violations},
            "wall_s": wall}


def test_chain_summary_reports_progress_per_session():
    rows = [_row(1), _row(3), _row(3), _row(6)]
    out = run_chain.chain_summary(rows)
    assert out["per_session_scores"] == [1, 3, 3, 6]
    assert out["per_session_gain"] == [2, 0, 3]
    assert out["stalled_sessions"] == 1, "a session that added nothing"
    assert out["final_milestone_score"] == 6


def test_chain_summary_survives_an_ungradeable_session():
    out = run_chain.chain_summary([_row(2), {"grade": {"parse_error": True},
                                             "wall_s": 1.0}])
    assert out["per_session_scores"] == [2]
    assert out["final_milestone_score"] is None


# --------------------------------------------------------------- resuming


def test_completed_sessions_counts_a_contiguous_run(tmp_path):
    for i in (1, 2, 3):
        (tmp_path / f"session-c01s{i:02d}.json").write_text("{}", encoding="utf-8")
    assert run_chain.completed_sessions(tmp_path, 1) == 3
    assert run_chain.completed_sessions(tmp_path, 2) == 0


def test_completed_sessions_stops_at_the_first_gap(tmp_path):
    """A hole means the chain state is not what a later session assumed."""
    for i in (1, 2, 4):
        (tmp_path / f"session-c01s{i:02d}.json").write_text("{}", encoding="utf-8")
    assert run_chain.completed_sessions(tmp_path, 1) == 2


def test_ungradeable_session_does_not_kill_the_chain(tmp_path, monkeypatch):
    """A session's own output can contain non-UTF-8 bytes.

    Without errors="replace" the subprocess reader thread dies and stdout
    comes back None — which took down a whole six-session chain mid-run.
    """
    import subprocess as sp

    class Broken:
        stdout = None

    monkeypatch.setattr(sp, "run", lambda *a, **k: Broken())
    out = run_chain.grade(tmp_path, tmp_path)
    assert out["parse_error"] is True


def test_the_budget_hook_finds_its_config_from_a_subdirectory(tmp_path):
    """세션이 하위 폴더에 가 있어도 예산이 깎이면 안 된다.

    2026-08-21에 실제로 그랬다. 훅이 받는 `cwd`가 작업 트리 뿌리가 아니면
    설정을 못 찾고 기본값 60으로 조용히 떨어져, 100으로 준 예산이 61호출에서
    잘렸다. 실패로도 안 보였다.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "casa_budget_subdir", ROOT / "pilot" / "chain_budget.py")
    budget = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(budget)

    work = tmp_path / "work"
    (work / "usagectl" / "readers").mkdir(parents=True)
    budget.install(work, 100)

    assert budget.load_config(work).get("budget") == 100
    assert budget.load_config(work / "usagectl").get("budget") == 100
    assert budget.load_config(work / "usagectl" / "readers").get("budget") == 100


# ------------- 첫 세션과 후속 세션에 다른 프롬프트를 준다 (2026-08-21)

def test_a_task_with_a_follow_up_prompt_gives_a_different_one_to_later_sessions(
        tmp_path):
    """사슬의 둘째 세션부터는 앞사람 일을 이어받는 자리다.

    지금까지는 다섯 세션이 전부 "릴리스를 준비해라"라는 같은 말을 받았다.
    """
    task = tmp_path / "task"
    task.mkdir()
    (task / "prompt.txt").write_text("처음부터 해줘\n", encoding="utf-8")
    (task / "prompt_followup.txt").write_text("이어서 해줘\n", encoding="utf-8")

    first, followup = run_chain.load_prompts(task)
    assert first.strip() == "처음부터 해줘"
    assert followup.strip() == "이어서 해줘"


def test_a_task_with_no_follow_up_prompt_reuses_the_first_one(tmp_path):
    """사슬이 아닌 과제와 옛 과제 11종이 그렇다."""
    task = tmp_path / "task"
    task.mkdir()
    (task / "prompt.txt").write_text("하나뿐인 프롬프트\n", encoding="utf-8")

    first, followup = run_chain.load_prompts(task)
    assert first == followup


def test_the_runner_hands_the_first_prompt_only_to_session_one():
    """소스에서 확인한다. 배선을 잊으면 파일만 만들고 아무 일도 안 일어난다."""
    source = (Path(run_chain.__file__)).read_text(encoding="utf-8")
    assert "first_prompt if index == 1 else next_prompt" in source

def test_the_served_model_is_recorded_for_every_session():
    """사전 예측 문서가 모델을 조건으로 적는데, 그것을 확인하는 기록이
    지금까지 없었다.

    `--model` 을 안 주면 CLI 기본값이 쓰이고 `meta.json` 에는 `null` 이
    남는다. 2026-08-21에 서브시스템 보정 배치 4차를 그렇게 시작했다.
    """
    cli = {"modelUsage": {"claude-sonnet-5": {"costUSD": 3.16},
                          "claude-haiku-4-5-20251001": {"costUSD": 0.001}}}
    assert run_chain.served_models(cli) == ["claude-haiku-4-5-20251001",
                                            "claude-sonnet-5"]


def test_a_session_with_no_usage_record_lists_no_model():
    """CLI가 시작조차 못 하면 사용량 기록이 없다. 없는 것을 지어내지 않는다."""
    assert run_chain.served_models({"parse_error": True, "exit_code": 1}) == []
    assert run_chain.served_models({}) == []


def test_every_session_row_carries_the_served_model():
    source = (ROOT / "pilot" / "run_chain.py").read_text(encoding="utf-8")
    assert '"served_models": served_models(cli),' in source
