"""Tests for the pure/local parts of the pilot session runner.

The headless-CLI path needs an authenticated `claude` binary and is
exercised by the W1.5 vertical slice, not unit tests.
"""

import importlib.util
import os
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


def test_is_infra_failure_matches_real_429_payload():
    # Shape observed in W8 when the usage limit was hit mid-batch.
    payload = {"type": "result", "is_error": True, "api_error_status": 429,
               "result": "You've hit your session limit · resets 1am"}
    assert run_sessions.is_infra_failure(payload)
    assert not run_sessions.is_infra_failure(
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


def test_prepare_workdir_ignores_the_callers_git_environment(tmp_path,
                                                             monkeypatch):
    """부모 git 프로세스의 색인을 물려받으면 안 된다.

    `git commit -a` 는 훅에 `GIT_INDEX_FILE` 을 절대 경로(부모 저장소의
    `.git/index.lock`)로 넘긴다. 우리 pre-commit 훅이 테스트를 실행하므로 이
    함수의 git 이 그 값을 그대로 물려받았고, 임시 작업 디렉토리의 `git add` 가
    부모 색인에 항목을 써서 이어지는 커밋이 객체를 찾지 못했다.
    """
    task_dir = REPO / "pilot" / "tasks" / "buggy-pipeline"
    outside = tmp_path / "outside.index"
    monkeypatch.setenv("GIT_INDEX_FILE", str(outside))
    monkeypatch.setenv("GIT_AUTHOR_NAME", "somebody-else")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "else@example.invalid")

    dest = run_sessions.prepare_workdir(task_dir, tmp_path / "w")

    assert not outside.exists(), "부모 쪽 색인 파일을 건드렸다"
    log = subprocess.run(["git", "log", "-1", "--format=%an %s"], cwd=dest,
                         capture_output=True, text=True, check=True,
                         env=run_sessions._git_env())
    assert log.stdout.strip() == "pilot initial state"


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

    # 임시 저장소를 확인하는 git 도 호출한 쪽의 환경을 물려받으면 안 된다.
    # 물려받으면 `git status` 가 이 작업 디렉토리를 부모 저장소의 색인과
    # 견주게 되어 전부 변경으로 나온다.
    log = subprocess.run(["git", "log", "--oneline"], cwd=workdir,
                         capture_output=True, text=True,
                         env=run_sessions._git_env())
    assert log.returncode == 0 and "initial state" in log.stdout
    status = subprocess.run(["git", "status", "--porcelain"], cwd=workdir,
                            capture_output=True, text=True,
                            env=run_sessions._git_env())
    assert status.stdout.strip() == ""


def test_ensure_task_venv_none_without_requirements(tmp_path):
    # buggy-pipeline is a stdlib task (no template/requirements.txt) -> None,
    # and no venv is created.
    task_dir = REPO / "pilot" / "tasks" / "buggy-pipeline"
    assert run_sessions.ensure_task_venv(task_dir, tmp_path) is None
    assert not (tmp_path / ".taskvenv").exists()


def test_venv_bin_dir_per_os():
    import os
    from pathlib import Path
    got = run_sessions.venv_bin_dir(Path("x") / ".taskvenv")
    assert got.name == ("Scripts" if os.name == "nt" else "bin")


def test_session_env_prepends_task_venv_to_path(tmp_path):
    import os
    base = run_sessions._session_env(None)
    assert base == run_sessions._child_env()          # no venv -> unchanged
    binp = tmp_path / "Scripts"
    env = run_sessions._session_env(binp)
    assert env["PATH"].split(os.pathsep)[0] == str(binp)


def test_the_child_env_sets_the_sandbox_flag_the_cli_accepts_when_root():
    """root로 실행되면 `IS_SANDBOX`가 정확히 `1`이어야 한다.

    CLI는 root로 `--dangerously-skip-permissions`를 쓰면 시작을 거부하고,
    `IS_SANDBOX=1`만 그 예외로 받는다. 컨테이너가 설정해 두는 `yes` 같은
    값은 받지 않는다. 2026-08-21에 서브시스템 보정 배치 4차가 그것 때문에
    세션 둘을 각각 0.8초 만에 끝냈다 — 러너는 정상 종료로 기록했다.
    """
    env = {"IS_SANDBOX": "yes"}
    run_sessions._allow_root_skip_permissions(env)
    if getattr(os, "geteuid", None) is not None and os.geteuid() == 0:
        assert env["IS_SANDBOX"] == "1"
    else:
        assert env["IS_SANDBOX"] == "yes", "root가 아니면 건드리지 않는다"


def test_the_sandbox_flag_is_not_forced_when_not_root():
    """유저 장비에서는 이 예외가 필요 없다. 값을 만들어 넣지 않는다."""
    import unittest.mock

    env: dict[str, str] = {}
    # Windows 에는 `os.geteuid` 가 아예 없어서 `create=True` 없이는 이 테스트
    # 자체가 AttributeError 로 실패한다. 판정 대상은 root 가 아닐 때의 동작이다.
    with unittest.mock.patch.object(os, "geteuid", return_value=1000, create=True):
        run_sessions._allow_root_skip_permissions(env)
    assert env == {}


def test_the_sandbox_flag_is_not_forced_where_there_is_no_geteuid():
    """`os.geteuid` 가 없는 Windows 에서도 예외를 내지 않고 지나가야 한다."""
    import unittest.mock

    env = {"IS_SANDBOX": "yes"}
    with unittest.mock.patch.object(os, "geteuid", None, create=True):
        run_sessions._allow_root_skip_permissions(env)
    assert env == {"IS_SANDBOX": "yes"}


def test_ml_shift_task_has_requirements():
    # the ML arm task DOES ship requirements -> ensure_task_venv would build.
    req = REPO / "pilot" / "tasks" / "ml-shift" / "template" / "requirements.txt"
    assert req.exists() and "scikit-learn" in req.read_text(encoding="utf-8")


def test_timeout_payload_is_not_infra_failure():
    # A single over-long session (subprocess timeout) is a task-level failure,
    # not an infra abort: the batch must continue, not stop.
    payload = {"timed_out": True, "is_error": True, "exit_code": -1,
               "result": "session exceeded 1500s timeout"}
    assert run_sessions.is_infra_failure(payload) is False


def test_a_session_the_cli_never_started_is_recognized():
    """CLI가 결과 JSON을 한 줄도 안 내고 종료 코드를 남긴 경우.

    2026-08-21에 관측된 모양이다. 컨테이너가 root로 돌고 있어 CLI가
    `--dangerously-skip-permissions`를 거부했다.
    """
    payload = {"parse_error": True, "stdout_tail": "",
               "stderr_tail": "--dangerously-skip-permissions cannot be used "
                              "with root/sudo privileges for security reasons\n",
               "exit_code": 1}
    assert run_sessions.session_never_started(payload) is True


def test_a_timed_out_session_did_start():
    """시간 제한에 도달한 세션은 실행됐다. 배치를 멈출 이유가 아니다."""
    payload = {"timed_out": True, "is_error": True, "exit_code": -1,
               "result": "session exceeded 1800s timeout"}
    assert run_sessions.session_never_started(payload) is False


def test_a_normal_session_did_start():
    payload = {"type": "result", "subtype": "success", "is_error": False,
               "result": "done", "exit_code": 0}
    assert run_sessions.session_never_started(payload) is False


def test_the_chain_runner_stops_when_a_session_never_started():
    """세션이 시작조차 못 했는데 다음 세션으로 넘어가면, 한 번도 실행되지
    않은 배치가 정상 완주로 기록된다. 러너 소스에서 그 처리를 확인한다."""
    source = (REPO / "pilot" / "run_chain.py").read_text(encoding="utf-8")
    assert "session_never_started(cli)" in source
    assert "raise SystemExit(3)" in source
