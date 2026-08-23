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


def test_the_session_is_told_to_wrap_up_before_it_is_blocked():
    """정리할 창이 없으면 어떤 세션도 인계 문서를 못 쓴다 — 파일을 쓰는 것도
    도구 호출이기 때문이다."""
    quiet, _ = chain_budget.decide(used=10, budget=60, warn_at=55)
    stop_code, stop_msg = chain_budget.decide(used=57, budget=60, warn_at=55)
    block_code, block_msg = chain_budget.decide(used=90, budget=60, warn_at=55)

    assert quiet == 0
    assert stop_code == 0 and "인계 문서" in stop_msg
    assert block_code == 2 and "더 이상 도구를 쓸 수 없다" in block_msg


def test_no_message_ever_tells_the_session_a_number():
    """**세션에게 남은 호출 수를 알려 주지 않는다**(2026-08-21 유저 지시).

    2026-08-21 보정 사슬 여덟 세션 전부가 종료 메시지에서 예산을 이유로 들었고
    넷은 그래서 편집을 시작하지 않았다고 적었다. 세션 4는 34/30에서 멈췄는데
    상한 45까지 11회가 남아 있었다. 남은 수를 알려 주는 한 세션은 그 수를 보고
    일을 조절하므로, 멈추는 자리를 측정 대상이 정하게 된다.
    """
    for used in (55, 57, 60, 61, 75, 89, 90, 200):
        _, message = chain_budget.decide(used, budget=60, warn_at=55)
        for number in ("55", "57", "60", "61", "75", "89", "90", "200"):
            assert number not in message, f"{used}회에서 수가 새어 나갔다: {message}"


def test_the_wrap_up_signal_is_sent_only_once():
    """호출마다 되풀이하면 들은 횟수로 위치를 셀 수 있게 되어, 수를 감춘 뜻이
    없어진다."""
    _, first = chain_budget.decide(used=55, budget=60, warn_at=55)
    _, again = chain_budget.decide(used=56, budget=60, warn_at=55,
                                   already_said=True)
    assert first and not again


def test_the_hard_cap_still_blocks():
    """세션이 정리 신호를 무시하고 계속 갈 때의 안전판이다."""
    below, _ = chain_budget.decide(used=89, budget=60, warn_at=55,
                                   already_said=True)
    at_cap, message = chain_budget.decide(used=90, budget=60, warn_at=55,
                                          already_said=True)
    assert below == 0
    assert at_cap == 2 and message


def test_the_hard_cap_is_half_again_the_budget():
    """예산 30이면 45다. 하던 서브시스템 하나를 끝내기에는 넉넉하고 두셋을
    더 하기에는 모자란다. 작은 예산에서는 최소 10회를 준다."""
    assert chain_budget.hard_cap_for(30) == 45
    assert chain_budget.hard_cap_for(60) == 90
    assert chain_budget.hard_cap_for(12) == 22


def test_the_config_carries_the_hard_cap(tmp_path):
    work = tmp_path / "chain-01"
    work.mkdir()
    chain_budget.install(work, budget=30)
    config = json.loads(
        (tmp_path / ".casa-chain.json").read_text(encoding="utf-8"))
    assert config == {"budget": 30, "warn_at": 25, "hard_cap": 45}


def test_the_config_is_kept_out_of_the_session_tree(tmp_path):
    """세션이 `ls` 한 번으로 예산과 상한을 볼 수 있으면, 훅 메시지에서 수를
    뺀 뜻이 없어진다. 그래서 작업 디렉토리 밖에 둔다."""
    work = tmp_path / "chain-01"
    work.mkdir()
    chain_budget.install(work, budget=30)
    assert not (work / ".casa-chain.json").exists()
    assert (tmp_path / ".casa-chain.json").exists()


def test_the_hook_still_finds_the_config_from_inside_the_workdir(tmp_path):
    """작업 트리 밖에 뒀는데 못 찾으면 훅이 아무것도 안 하게 된다. 세션이
    들어가 있을 만한 하위 폴더에서도 찾아야 한다."""
    work = tmp_path / "chain-01"
    (work / "opsbox" / "report").mkdir(parents=True)
    chain_budget.install(work, budget=30)
    assert chain_budget.load_config(work / "opsbox" / "report") == {
        "budget": 30, "warn_at": 25, "hard_cap": 45}


def test_the_wrap_up_marker_is_kept_out_of_the_session_tree(tmp_path):
    """이미 보냈는지를 적어 두는 파일도 세션이 보면 안 된다 — 있는 것만으로
    이 세션이 끝나 간다는 신호가 된다."""
    work = tmp_path / "chain-01"
    work.mkdir()
    chain_budget.install(work, budget=30)
    folder, _ = chain_budget.find_config(work)
    assert chain_budget._said_path(folder).parent == tmp_path


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
    work = tmp_path / "chain-01"
    work.mkdir()
    run_chain.install_budget(work, budget=60)
    # 설정은 작업 트리 밖, 훅 배선은 작업 트리 안이다 — CLI 가 훅을 프로젝트
    # 디렉토리에서 읽기 때문이다.
    config = json.loads((tmp_path / ".casa-chain.json").read_text(encoding="utf-8"))
    assert config == {"budget": 60, "warn_at": 55, "hard_cap": 90}

    settings = json.loads(
        (work / ".claude" / "settings.json").read_text(encoding="utf-8"))
    command = settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    assert "chain_budget.py" in command


def test_hook_is_installed_per_chain_not_globally(tmp_path):
    """A chain run must not leak its budget into the developer's own sessions."""
    work = tmp_path / "chain-01"
    work.mkdir()
    run_chain.install_budget(work, budget=60)
    assert (work / ".claude" / "settings.json").exists()
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


# ------------------------------- 예산을 없애고 시간으로만 제한하는 갈래

def test_a_budget_of_zero_wires_nothing(tmp_path):
    """세션에게 아무 신호도 주지 않는다 (2026-08-21 유저 지시).

    보정 사슬 여덟 세션 전부가 종료 메시지에서 예산을 이유로 들었고 넷은
    그래서 편집을 시작하지 않았다고 적었다. 세션 4는 34/30 에서 멈췄는데
    상한 45 까지 11회가 남아 있었다. 남은 호출 수를 알려 주는 한 세션은 그
    수를 보고 일을 조절한다.

    설정 파일도 훅 배선도 남지 않아야 한다. 설정만 지우고 훅을 남기면 훅이
    기본값 60 으로 떨어져 세션을 조용히 자른다 — 2026-08-21에 실제로 그렇게
    100 이 60 으로 깎였다.
    """
    chain_budget.install(tmp_path, budget=0)
    assert not (tmp_path / ".casa-chain.json").exists()
    assert not (tmp_path / ".claude" / "settings.json").exists()


def test_a_budget_of_zero_has_no_hard_cap():
    """호출 수로는 아무것도 제한하지 않는다."""
    assert chain_budget.hard_cap_for(0) is None
    assert chain_budget.hard_cap_for(-1) is None


def test_the_hook_says_nothing_when_there_is_no_budget():
    """예산이 없으면 경고도 초과 통지도 차단도 없다."""
    for used in (0, 1, 30, 300, 3000):
        code, message = chain_budget.decide(used, budget=0, warn_at=1)
        assert code == 0 and message == ""


def test_the_snapshot_hook_still_installs_with_no_budget(tmp_path):
    """예산 훅을 빼도 호출마다 찍는 스냅숏은 남아야 한다.

    스냅숏이 없으면 세션이 몇 호출째에 무엇을 고쳤는지 알 수 없고, 그것이
    이 갈래에서 유일하게 남는 진척 기록이다.
    """
    import snapshot

    chain_budget.install(tmp_path, budget=0)
    snapshot.install(tmp_path, tmp_path / "snap.git")
    settings = json.loads(
        (tmp_path / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert "PostToolUse" in settings["hooks"]
    assert "PreToolUse" not in settings["hooks"]


def test_every_session_row_records_whether_time_cut_it():
    """예산이 없으면 세션을 끊는 것은 시간뿐이다. 시간에 걸린 세션은 인계
    문서를 못 쓰고 끝나므로, 몇이 그렇게 끊겼는지가 기록에 남아야 한다."""
    source = (ROOT / "pilot" / "run_chain.py").read_text(encoding="utf-8")
    assert '"timed_out": bool(cli.get("timed_out")),' in source
    assert '"timeout_s": timeout_s,' in source


def _context(done) -> str:
    """훅이 낸 JSON 에서 세션에게 전해지는 글만 꺼낸다. 훅 출력은 아스키로
    이스케이프되므로 원문을 문자열로 맞대면 늘 어긋난다."""
    if not done.stdout.strip():
        return ""
    return json.loads(done.stdout)["hookSpecificOutput"]["additionalContext"]


def _run_hook(work: Path, transcript: Path):
    """훅을 **프로세스로** 부른다. 임포트로 부르면 배선과 표준입출력 계약을
    못 잡는다."""
    import subprocess
    payload = json.dumps({"cwd": str(work),
                          "transcript_path": str(transcript)})
    return subprocess.run(
        [sys.executable, str(ROOT / "pilot" / "chain_budget.py")],
        input=payload, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=60)


def test_the_hook_sends_the_wrap_up_signal_exactly_once(tmp_path):
    """`decide` 단위 테스트만으로는 부족하다 — 한 번만 보내는 것은 훅이
    보냈다는 사실을 어디에 적어 두는가에 달려 있고, 그 기억은 프로세스 밖에
    있다."""
    work = tmp_path / "chain-01"
    work.mkdir()
    chain_budget.install(work, budget=10, warn_margin=2)   # warn_at 8
    transcript = tmp_path / "t.jsonl"

    _transcript(transcript, 8)
    first = _run_hook(work, transcript)
    _transcript(transcript, 9)
    second = _run_hook(work, transcript)

    assert first.returncode == 0 and "인계 문서" in _context(first)
    assert second.returncode == 0 and second.stdout == "", (
        f"두 번째 호출에서도 보냈다: {second.stdout}")


def test_each_session_of_a_chain_gets_its_own_wrap_up_signal(tmp_path):
    """사슬의 세션들이 작업 디렉토리를 함께 쓴다. 세션마다 갈라 적지 않으면
    두 번째 세션부터는 정리 신호를 못 받고 상한에서 잘린다."""
    work = tmp_path / "chain-01"
    work.mkdir()
    chain_budget.install(work, budget=10, warn_margin=2)

    first = _run_hook(work, _transcript(tmp_path / "s01.jsonl", 8))
    second = _run_hook(work, _transcript(tmp_path / "s02.jsonl", 8))

    assert "인계 문서" in _context(first)
    assert "인계 문서" in _context(second)


def test_the_hook_blocks_at_the_cap_and_says_no_number(tmp_path):
    work = tmp_path / "chain-01"
    work.mkdir()
    chain_budget.install(work, budget=10, warn_margin=2)   # hard_cap 20
    done = _run_hook(work, _transcript(tmp_path / "t.jsonl", 20))
    assert done.returncode == 2
    for number in ("10", "20"):
        assert number not in done.stderr, f"수가 새어 나갔다: {done.stderr}"


def test_the_hook_does_nothing_when_it_cannot_find_the_config(tmp_path):
    """못 찾은 채로 기본값 60을 적용해 세션을 자르면 실행 기록에는 정상 종료로
    남는다. 2026-08-21에 100으로 준 예산이 그렇게 60으로 깎였다."""
    work = tmp_path / "chain-01"
    work.mkdir()
    done = _run_hook(work, _transcript(tmp_path / "t.jsonl", 999))
    assert done.returncode == 0 and done.stdout == ""


# ------- 호출 총량으로 세션 수를 정한다 (2026-08-22, 끊는 배치를 위해)

def test_the_runner_counts_calls_from_the_audit_not_the_turn_count():
    """어시스턴트 차례 수는 도구 호출 수와 다르다. 총량을 맞추려면 실제 호출
    수를 세야 한다."""
    row = {"audit": {"metrics": {"n_tool_calls": 28}},
           "cli": {"num_turns": 42}}
    assert run_chain.calls_of(row) == 28
    assert run_chain.calls_of({}) == 0


def test_earlier_rows_are_read_back_for_resuming(tmp_path):
    """이어서 진행할 때 앞서 쓴 호출 수를 이어 세지 않으면 총량이 두 배가
    된다."""
    for index, calls in ((1, 30), (2, 12)):
        (tmp_path / f"session-c01s{index:02d}.json").write_text(
            json.dumps({"audit": {"metrics": {"n_tool_calls": calls}}}),
            encoding="utf-8")
    (tmp_path / "session-c02s01.json").write_text(
        json.dumps({"audit": {"metrics": {"n_tool_calls": 99}}}),
        encoding="utf-8")

    got = run_chain.earlier_rows(tmp_path, 1)
    assert [run_chain.calls_of(r) for r in got] == [30, 12], "다른 사슬이 섞였다"


def test_a_broken_session_record_does_not_stop_the_count(tmp_path):
    (tmp_path / "session-c01s01.json").write_text("{깨진", encoding="utf-8")
    assert run_chain.earlier_rows(tmp_path, 1) == []


def test_the_session_cap_bounds_the_allowance_loop():
    """끊는 조건에서는 세션이 열 호출 만에 끝나므로 총량이 다 되기까지 세션이
    여럿 필요하다. 무한히 돌지는 않아야 한다."""
    assert run_chain.MAX_SESSIONS_PER_CHAIN >= 20


def test_the_allowance_and_the_cut_point_are_recorded_in_every_row():
    """두 조건을 나중에 가르려면 기록에 조건이 남아 있어야 한다."""
    source = (ROOT / "pilot" / "run_chain.py").read_text(encoding="utf-8")
    assert '"cut_at": cut_at,' in source
    assert '"call_allowance": allowance,' in source
    assert '"calls_used_in_chain"' in source


# --------------------------------- 재개할 때 연속 끊기 횟수를 이어받는다

def test_the_cut_streak_is_carried_over_when_a_chain_resumes():
    """0에서 다시 세면 상한을 넘겨 끊는다.

    2026-08-22 배치에서 실제로 그 자리에 있었다. 사슬 하나가 끊긴 세션으로
    끝난 채 외부에서 종료됐고, 그대로 이어 실행했다면 상한이 2인데 세 세션이
    연달아 끊길 수 있었다.
    """
    rows = [{"cut": False}, {"cut": True}, {"cut": True}]
    assert run_chain.trailing_cut_streak(rows) == 2


def test_a_chain_that_ended_on_a_finished_session_carries_no_streak():
    rows = [{"cut": True}, {"cut": True}, {"cut": False}]
    assert run_chain.trailing_cut_streak(rows) == 0


def test_no_earlier_sessions_means_no_streak():
    assert run_chain.trailing_cut_streak([]) == 0


def test_a_row_without_the_cut_field_ends_the_streak():
    """옛 배치의 기록에는 `cut` 이 없다. 없으면 안 끊긴 것으로 본다."""
    assert run_chain.trailing_cut_streak([{"cut": True}, {}]) == 0
