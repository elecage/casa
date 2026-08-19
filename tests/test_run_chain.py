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
    stop_code, stop_msg = chain_budget.decide(used=60, budget=60, warn_at=55)

    assert quiet == 0
    assert warn_code == 0 and "3회 남았다" in warn_msg
    assert stop_code == 2 and "예산 소진" in stop_msg


def test_warning_says_how_many_are_left():
    _, message = chain_budget.decide(used=55, budget=60, warn_at=55)
    assert "55/60" in message and "5회" in message


def test_over_budget_stays_blocked():
    code, _ = chain_budget.decide(used=999, budget=60, warn_at=55)
    assert code == 2


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
    assert config == {"budget": 60, "warn_at": 55}

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
