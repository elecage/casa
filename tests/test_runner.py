"""Tests for the pure/local parts of the pilot session runner.

The headless-CLI path needs an authenticated `claude` binary and is
exercised by the W1.5 vertical slice, not unit tests.
"""

import importlib.util
import subprocess
from pathlib import Path

REPO = Path(__file__).parent.parent

spec = importlib.util.spec_from_file_location(
    "run_sessions", REPO / "pilot" / "run_sessions.py")
run_sessions = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_sessions)


def test_pending_indices_skips_completed_sessions(tmp_path):
    (tmp_path / "session-01.json").write_text("{}", encoding="utf-8")
    (tmp_path / "session-03.json").write_text("{}", encoding="utf-8")
    assert run_sessions.pending_indices(tmp_path, 4) == [2, 4]


def test_is_auth_failure_matches_real_401_payload():
    # Shape observed in the W1.5 slice when the OAuth token had expired.
    payload = {"type": "result", "subtype": "success", "is_error": True,
               "api_error_status": 401,
               "result": "Failed to authenticate. API Error: 401 OAuth access "
                         "token has expired. Re-authenticate to continue."}
    assert run_sessions.is_auth_failure(payload)
    assert not run_sessions.is_auth_failure(
        {"is_error": False, "result": "OK", "api_error_status": None})
    assert not run_sessions.is_auth_failure(
        {"is_error": True, "result": "tool timeout", "api_error_status": None})


def test_summarize_aggregates_session_rows():
    rows = [
        {"session_index": 1, "wall_s": 100.0,
         "cli": {"total_cost_usd": 0.30},
         "audit": {"violations": [], "metrics": {"coverage": 1.0,
                                                 "exploration_before_first_edit": 11}},
         "grade": {"success": True}},
        {"session_index": 2, "wall_s": 90.0,
         "cli": {"total_cost_usd": 0.20},
         "audit": {"violations": [{"rule_id": "canary-no-cat"}],
                   "metrics": {"coverage": 0.5,
                               "exploration_before_first_edit": 3}},
         "grade": {"success": False}},
    ]
    summary = run_sessions.summarize(rows)
    assert summary["n"] == 2 and summary["successes"] == 1
    assert summary["success_rate"] == 0.5
    assert summary["mean_cost_usd"] == 0.25
    assert summary["sessions"][1]["violations"] == 1
    assert summary["sessions"][0]["coverage"] == 1.0


def test_prepare_workdir_wipes_leftover_dest(tmp_path):
    task_dir = REPO / "pilot" / "tasks" / "buggy-pipeline"
    dest = tmp_path / "w"
    dest.mkdir()
    (dest / "stale.txt").write_text("leftover", encoding="utf-8")
    run_sessions.prepare_workdir(task_dir, dest)
    assert not (dest / "stale.txt").exists()
    assert (dest / "CLAUDE.md").exists()


def test_prepare_workdir_wipes_readonly_leftovers(tmp_path):
    # Windows git object files are read-only; a crashed session's workdir
    # must still be removable (regression: WinError 5 on .git/objects).
    import os
    import stat

    task_dir = REPO / "pilot" / "tasks" / "buggy-pipeline"
    dest = tmp_path / "w"
    (dest / ".git" / "objects").mkdir(parents=True)
    locked = dest / ".git" / "objects" / "ab12cd"
    locked.write_text("x", encoding="utf-8")
    os.chmod(locked, stat.S_IREAD)

    run_sessions.prepare_workdir(task_dir, dest)
    assert not locked.exists()
    assert (dest / "CLAUDE.md").exists()


def test_rules_for_prefers_task_local_rules():
    tasks = REPO / "pilot" / "tasks"
    assert run_sessions.rules_for(tasks / "plugin-add") == \
        tasks / "plugin-add" / "canary_rules.yaml"
    assert run_sessions.rules_for(tasks / "buggy-pipeline") == \
        REPO / "rules" / "canary_rules.yaml"


def test_munge_matches_claude_code_convention():
    assert run_sessions.munge_project_dir(r"E:\Claude_Prjs\casa") == "E--Claude-Prjs-casa"
    assert run_sessions.munge_project_dir("/home/u/proj.x") == "-home-u-proj-x"


def test_prepare_workdir_copies_template_only_and_commits(tmp_path):
    task_dir = REPO / "pilot" / "tasks" / "buggy-pipeline"
    workdir = run_sessions.prepare_workdir(task_dir, tmp_path / "w")

    assert (workdir / "CLAUDE.md").exists()
    assert (workdir / "src" / "loglab" / "windowing.py").exists()
    # solution must never leak into the session's working copy
    assert not (workdir / "solution").exists()
    assert list(workdir.rglob("solution")) == []

    log = subprocess.run(["git", "log", "--oneline"], cwd=workdir,
                         capture_output=True, text=True)
    assert log.returncode == 0 and "initial state" in log.stdout
    status = subprocess.run(["git", "status", "--porcelain"], cwd=workdir,
                            capture_output=True, text=True)
    assert status.stdout.strip() == ""
