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
