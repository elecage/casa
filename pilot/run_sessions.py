#!/usr/bin/env python3
"""Pilot session runner (draft — W1.5 vertical slice, completed in W4).

Repeatedly runs Claude Code headless on a copy of a pilot task template,
then audits the transcript with CASA and grades the outcome:

    .venv/Scripts/python.exe pilot/run_sessions.py pilot/tasks/buggy-pipeline \
        -n 2 --out results/slice

Per session: copy template -> git init -> `claude -p <prompt> --output-format
json --dangerously-skip-permissions` -> locate the session transcript under
~/.claude/projects/ -> casa audit (canary rules + relevant files) -> task
grade.py -> one JSON summary per session.

Requires an authenticated Claude Code CLI (`claude auth login`).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from casa.audit import audit_session  # noqa: E402
from casa.rules import load_rules  # noqa: E402
import chain_budget  # noqa: E402
import snapshot  # noqa: E402

CANARY_RULES = REPO / "rules" / "canary_rules.yaml"


def rules_for(task_dir: Path) -> Path | None:
    """이 과제에 적용할 캐너리 규칙 파일. **없으면 `None` 이다.**

    과제에 둔 `canary_rules.yaml` 이 기본값보다 앞선다 — 과제마다 구체화한
    것(예: `plugin-add` 의 search-before-write 전제)이 있다.

    **규칙을 세션에게 말하지 않는 과제에는 적용하지 않는다** (2026-08-28,
    `docs/QUEUE_TASK_DEFECTS.md` 10-1). `rules/canary_rules.yaml` 머리에
    적혀 있듯이 이 규칙들은 **과제 저장소의 `CLAUDE.md` 에 자연어로 같이
    적혀 있어야** 하고, CASA 가 재는 것은 세션이 그 파일을 지키는지다. 옛 과제
    열한 종은 `template/CLAUDE.md` 에 그 여덟 줄을 담고 있다. 뒤에 만든 과제들
    (`queue-flat` 포함)은 담고 있지 않은데도 채점만 되고 있었다 — 2026-08-27
    실측이 셸 `cat` 과 `grep` 두 건을 위반으로 기록했는데, 그 세션은 그러지
    말라는 말을 어디서도 받지 않았다.
    """
    local = task_dir / "canary_rules.yaml"
    if local.exists():
        return local
    return CANARY_RULES if (task_dir / "template" / "CLAUDE.md").is_file() else None


def munge_project_dir(path: str | Path) -> str:
    """Claude Code names the transcript directory by replacing every
    non-alphanumeric character of the absolute cwd with '-'
    (e.g. ``E:\\Claude_Prjs\\casa`` -> ``E--Claude-Prjs-casa``)."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


def transcript_dir_for(workdir: Path) -> Path:
    return Path.home() / ".claude" / "projects" / munge_project_dir(workdir.resolve())


def _rmtree_force(path: Path) -> None:
    """rmtree that also removes read-only files - on Windows, git object
    files are read-only and plain rmtree dies with PermissionError."""
    def clear_readonly(func, target, _exc):
        os.chmod(target, stat.S_IWRITE)
        func(target)
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=clear_readonly)
    else:
        shutil.rmtree(path, onerror=clear_readonly)


#: git 이 자기 하위 프로세스에 넘기는 실행별 변수. 다른 저장소에서 git 을
#: 실행할 때 이 값들이 남아 있으면 그 저장소가 아니라 **부모 쪽의 색인과
#: 신원**을 쓴다.
#:
#: 이 저장소에서 실제로 문제가 됐다. `git commit -a` 는 훅에
#: `GIT_INDEX_FILE` 을 **절대 경로**(부모 저장소의 `.git/index.lock`)로 넘기고,
#: 우리 pre-commit 훅이 테스트를 실행하므로 `prepare_workdir` 의 git 이 그
#: 색인을 그대로 물려받았다. 임시 작업 디렉토리에서 `git add` 가 부모 색인에
#: 항목을 쓰고, 이어지는 `git commit` 이 그 색인이 가리키는 객체를 임시
#: 저장소에서 찾지 못해 `error: invalid object ... for 'data/sample.csv'` 로
#: 중단됐다. `git add` 로 따로 올린 뒤 커밋하면 `GIT_INDEX_FILE` 이 상대
#: 경로여서 드러나지 않는다 — 그래서 `-a` 를 쓸 때만 실패했다.
_GIT_ENV_KEYS = (
    "GIT_INDEX_FILE", "GIT_DIR", "GIT_WORK_TREE", "GIT_PREFIX",
    "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_AUTHOR_DATE",
    "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL", "GIT_COMMITTER_DATE",
)


def _git_env() -> dict[str, str]:
    """부모 git 프로세스의 실행별 변수를 제거한 환경.

    신원 변수(`GIT_AUTHOR_*`·`GIT_COMMITTER_*`)도 제거한다. 그 값이 남아 있으면
    아래 `-c user.name=pilot` 보다 우선하므로, 시작 상태 커밋의 작성자가 그때
    누가 실행했느냐에 따라 달라진다.
    """
    env = dict(os.environ)
    for key in _GIT_ENV_KEYS:
        env.pop(key, None)
    return env


def prepare_workdir(task_dir: Path, dest: Path) -> Path:
    """Copy the task template (never solution/ etc.) and make it a git repo
    with an initial commit, so the session can follow 'commit your changes'.
    An existing dest (leftover of a crashed session) is wiped first."""
    if dest.exists():
        _rmtree_force(dest)
    shutil.copytree(task_dir / "template", dest)
    run = lambda *cmd: subprocess.run(cmd, cwd=dest, check=True,
                                      capture_output=True, env=_git_env())
    run("git", "init", "-q", "-b", "main")
    run("git", "-c", "user.name=pilot", "-c", "user.email=pilot@casa.local",
        "add", "-A")
    run("git", "-c", "user.name=pilot", "-c", "user.email=pilot@casa.local",
        "commit", "-q", "-m", "initial state")
    return dest


def check_auth() -> tuple[bool, str]:
    """`claude auth status` gate: never start a batch on expired credentials
    (G1: an expired OAuth token fails every session in seconds)."""
    proc = subprocess.run("claude auth status", capture_output=True,
                          text=True, shell=True, env=_child_env())
    try:
        status = json.loads(proc.stdout)
        return bool(status.get("loggedIn")), status.get("email", "?")
    except json.JSONDecodeError:
        # Some versions print human-readable text; fall back to a marker.
        ok = "logged in" in proc.stdout.lower() or "loggedin" in proc.stdout.lower()
        return ok, "?"


def is_infra_failure(cli_payload: dict) -> bool:
    """True when a session died on infrastructure rather than the task -
    expired auth (401) or usage limit (429). Continuing would fail every
    later session the same way and record poisoned rows; W8 hit exactly
    this with 429 "session limit" responses recorded as task failures."""
    if cli_payload.get("api_error_status") in (401, 429):
        return True
    text = str(cli_payload.get("result", ""))
    return cli_payload.get("is_error", False) and (
        "OAuth" in text or "authenticate" in text.lower()
        or "limit" in text.lower())


def is_auth_failure(cli_payload: dict) -> bool:  # backward-compat alias
    return is_infra_failure(cli_payload)


def session_never_started(cli_payload: dict) -> bool:
    """CLI가 세션을 아예 시작하지 못했는가.

    `is_infra_failure`와 다른 것을 본다. 그쪽은 CLI가 **응답을 낸 뒤** 그
    응답이 401·429인 경우다. 이쪽은 CLI가 **결과 JSON을 한 줄도 내지 않고**
    종료 코드를 남기고 끝난 경우다 — 실행 파일이 없거나, 플래그를 거부하거나,
    시작 조건이 안 맞는 경우다.

    **왜 따로 봐야 하나.** 2026-08-21에 컨테이너가 root로 돌고 있어 CLI가
    `--dangerously-skip-permissions`를 거부했다. 세션마다 0.8초 만에 종료
    코드 1로 끝났는데, 러너는 그것을 정상 종료로 기록하고 다음 세션으로
    넘어갔다. 다섯 세션이 그렇게 기록됐고 채점 결과에는 시작 상태가 그대로
    남았다. 배치를 끝까지 돌렸다면 **세션 열 개가 한 번도 실행되지 않은
    배치가 정상 완주로 기록됐을 것이다.**

    시간 제한에 도달한 세션은 여기 해당하지 않는다 — 그 세션은 실행됐다.
    """
    if cli_payload.get("timed_out"):
        return False
    return bool(cli_payload.get("parse_error")) and bool(
        cli_payload.get("exit_code"))


def pending_indices(out_dir: Path, n: int) -> list[int]:
    """Resume support: sessions with an existing summary JSON are done."""
    return [i for i in range(1, n + 1)
            if not (out_dir / f"session-{i:02d}.json").exists()]


def summarize(rows: list[dict]) -> dict:
    def _m(row: dict, *keys, default=None):
        cur = row
        for key in keys:
            if not isinstance(cur, dict):
                return default
            cur = cur.get(key, default)
        return cur

    sessions = []
    for row in rows:
        sessions.append({
            "index": row.get("session_index"),
            "success": bool(_m(row, "grade", "success", default=False)),
            "wall_s": row.get("wall_s"),
            "cost_usd": _m(row, "cli", "total_cost_usd"),
            "violations": len(_m(row, "audit", "violations", default=[]) or []),
            "coverage": _m(row, "audit", "metrics", "coverage"),
            "exploration_before_first_edit":
                _m(row, "audit", "metrics", "exploration_before_first_edit"),
        })
    n = len(sessions)
    successes = sum(1 for s in sessions if s["success"])
    costs = [s["cost_usd"] for s in sessions if isinstance(s["cost_usd"], (int, float))]
    return {
        "n": n,
        "successes": successes,
        "success_rate": round(successes / n, 3) if n else None,
        "mean_cost_usd": round(sum(costs) / len(costs), 3) if costs else None,
        "sessions": sessions,
    }


def _child_env() -> dict[str, str]:
    env = dict(os.environ)
    for key in list(env):
        if key.startswith(("CLAUDECODE", "CLAUDE_CODE_")):
            env.pop(key)
    _allow_root_skip_permissions(env)
    return env


def _allow_root_skip_permissions(env: dict[str, str]) -> None:
    """uid 0으로 실행 중이면 `IS_SANDBOX`를 `1`로 맞춘다.

    CLI는 root로 `--dangerously-skip-permissions`를 쓰면 시작하지 않고
    "cannot be used with root/sudo privileges for security reasons"를 stderr에
    출력한 뒤 종료 코드 1로 끝난다. `IS_SANDBOX=1`이 그 예외다.

    **컨테이너가 `IS_SANDBOX=yes`를 설정해 두는 경우가 있고, CLI는 그 값을
    받지 않는다.** 2026-08-21에 서브시스템 보정 배치 4차가 그것 때문에
    세션 둘을 각각 0.8초 만에 끝냈다 — 세션은 한 번도 시작하지 않았는데
    러너는 정상 종료로 기록했고, 채점 결과에는 시작 상태 1/17이 그대로
    남았다. 이 프로젝트에서 네 번째로 겪은 "테스트는 통과하는데 수집만
    깨지는" 결함이다.

    uid 0이 아니면 아무것도 하지 않는다 — 유저 장비에서는 이 예외가
    필요하지 않다. `os.geteuid`가 없는 Windows에서도 아무것도 하지 않는다.
    """
    if getattr(os, "geteuid", None) is None or os.geteuid() != 0:
        return
    env["IS_SANDBOX"] = "1"


def venv_bin_dir(venv: Path) -> Path:
    """The Scripts/ (Windows) or bin/ (POSIX) directory of a venv."""
    return venv / ("Scripts" if os.name == "nt" else "bin")


def ensure_task_venv(task_dir: Path, out_dir: Path) -> Path | None:
    """Tasks with ML/native deps ship template/requirements.txt; create a
    per-batch venv once (out_dir/.taskvenv) with those deps and return its
    bin dir, so the session's `python` resolves to an interpreter that has
    them. Stdlib tasks (no requirements.txt) return None. The venv is reused
    across every session in the batch, not recreated per session."""
    req = task_dir / "template" / "requirements.txt"
    if not req.exists():
        return None
    venv = out_dir / ".taskvenv"
    bind = venv_bin_dir(venv)
    py = bind / ("python.exe" if os.name == "nt" else "python")
    if not py.exists():
        print(f"task venv: creating + installing {req.name} ...", flush=True)
        subprocess.run([sys.executable, "-m", "venv", str(venv)],
                       check=True, capture_output=True)
        subprocess.run([str(py), "-m", "pip", "install", "-q", "-r", str(req)],
                       check=True, capture_output=True, timeout=1800)
    return bind


def _session_env(venv_bin: Path | None = None) -> dict[str, str]:
    """Child env for a session; prepends a task venv's bin dir to PATH so the
    session's bare `python`/`pytest` use the task interpreter."""
    env = _child_env()
    if venv_bin is not None:
        env["PATH"] = str(venv_bin) + os.pathsep + env.get("PATH", "")
    return env


def run_headless(workdir: Path, prompt: str, model: str | None,
                 timeout_s: int, venv_bin: Path | None = None) -> dict:
    # The prompt goes through stdin, never the command line: on Windows the
    # command runs via the shell (npm .cmd shim), and cmd.exe mangles
    # multi-line arguments. The command string itself carries flags only.
    cmd = "claude -p --output-format json --dangerously-skip-permissions"
    if model:
        cmd += f" --model {model}"
    try:
        proc = subprocess.run(cmd, cwd=workdir, input=prompt,
                              capture_output=True, text=True,
                              encoding="utf-8", errors="replace",
                              timeout=timeout_s, env=_session_env(venv_bin), shell=True)
    except subprocess.TimeoutExpired:
        # One over-long session must not crash the whole batch: record it as
        # a (task-level) timeout failure and let the loop continue. This is
        # NOT an infra failure, so is_infra_failure stays False and the run
        # proceeds to the next session.
        return {"timed_out": True, "is_error": True, "exit_code": -1,
                "result": f"session exceeded {timeout_s}s timeout"}
    try:
        payload = json.loads(proc.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        payload = {"parse_error": True, "stdout_tail": proc.stdout[-1000:],
                   "stderr_tail": proc.stderr[-1000:]}
    payload["exit_code"] = proc.returncode
    return payload


def run_one(task_dir: Path, out_dir: Path, index: int, model: str | None,
            timeout_s: int, venv_bin: Path | None = None,
            budget: int | None = None) -> dict:
    prompt = (task_dir / "prompt.txt").read_text(encoding="utf-8")
    relevant = [ln.strip() for ln in
                (task_dir / "relevant_files.txt").read_text(encoding="utf-8").splitlines()
                if ln.strip()]
    workdir = prepare_workdir(task_dir, out_dir / f"work-{index:02d}")
    # 호출 단위 스냅숏. 작업 트리 밖의 저장소에 찍으므로 세션 쪽에는 흔적이
    # 남지 않는다 (docs/RECOVERY_RULE.md 4절).
    if budget:
        # 안전판이다. 끊는 장치가 아니라, 세션이 제 발로 멈추지 않을 때의
        # 상한이다. 걸리면 그 자체가 관측 결과다.
        chain_budget.install(workdir, budget)
    snapshot.install(workdir, out_dir / "snapshots" / f"work-{index:02d}.git")

    t0 = time.time()
    cli = run_headless(workdir, prompt, model, timeout_s, venv_bin)
    wall_s = round(time.time() - t0, 1)
    # 마지막 한 번. 세션의 끝 편집은 훅이 못 잡고 끝나는 수가 있다
    # (2026-08-20 프로브에서 여섯 중 하나가 그랬다).
    snapshot.take(workdir)

    summary: dict = {"task": task_dir.name, "session_index": index,
                     "wall_s": wall_s, "cli": cli}

    session_id = cli.get("session_id")
    tdir = transcript_dir_for(workdir)
    transcript = tdir / f"{session_id}.jsonl" if session_id else None
    if (transcript is None or not transcript.exists()) and tdir.exists():
        # Fallback: newest transcript for this workdir (session_id missing
        # from CLI output, e.g. after an output-parse failure).
        candidates = sorted(tdir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
        transcript = candidates[-1] if candidates else None
    if transcript and transcript.exists():
        saved = out_dir / f"transcript-{index:02d}.jsonl"
        shutil.copyfile(transcript, saved)
        summary["transcript"] = str(saved)
        rules_path = rules_for(task_dir)
        summary["audit"] = audit_session(
            saved, rules=load_rules(rules_path) if rules_path else None,
                                         relevant_files=relevant)
    else:
        summary["transcript"] = None

    grade = subprocess.run([sys.executable, str(task_dir / "grade.py"), str(workdir)],
                           capture_output=True, text=True, timeout=600)
    try:
        summary["grade"] = json.loads(grade.stdout)
    except json.JSONDecodeError:
        summary["grade"] = {"parse_error": True, "tail": grade.stdout[-500:]}

    (out_dir / f"session-{index:02d}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def _write_summary(out_dir: Path, n: int) -> dict:
    rows = []
    for i in range(1, n + 1):
        path = out_dir / f"session-{i:02d}.json"
        if path.exists():
            rows.append(json.loads(path.read_text(encoding="utf-8")))
    summary = summarize(rows)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("task_dir")
    ap.add_argument("-n", "--sessions", type=int, default=1)
    ap.add_argument("--out", default="results/slice")
    ap.add_argument("--model", default=None)
    ap.add_argument("--timeout-min", type=int, default=25)
    ap.add_argument("--budget", type=int, default=None,
                    help="도구 호출 상한(안전판). 없으면 상한 없음")
    ap.add_argument("--sleep-s", type=int, default=0,
                    help="pause between sessions")
    args = ap.parse_args()

    task_dir = Path(args.task_dir).resolve()
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    logged_in, email = check_auth()
    if not logged_in:
        print("ABORT: claude CLI is not authenticated - run `claude auth login` "
              "and re-run; finished sessions are kept and will be skipped.",
              file=sys.stderr)
        return 2

    version = subprocess.run("claude --version", capture_output=True,
                             text=True, shell=True).stdout.strip()
    venv_bin = ensure_task_venv(task_dir, out_dir)
    (out_dir / "meta.json").write_text(json.dumps({
        "claude_version": version, "task": task_dir.name,
        "sessions": args.sessions, "model": args.model, "account": email,
        "task_venv": str(venv_bin) if venv_bin else None,
    }, indent=2), encoding="utf-8")

    todo = pending_indices(out_dir, args.sessions)
    skipped = args.sessions - len(todo)
    if skipped:
        print(f"resume: {skipped} session(s) already done, "
              f"{len(todo)} to run", flush=True)

    aborted = False
    for pos, i in enumerate(todo):
        print(f"[{i}/{args.sessions}] running...", flush=True)
        s = run_one(task_dir, out_dir, i, args.model,
                    args.timeout_min * 60, venv_bin, args.budget)
        success = bool(s.get("grade", {}).get("success"))
        print(f"  success={success} wall={s['wall_s']}s "
              f"violations={len(s.get('audit', {}).get('violations', []))}",
              flush=True)
        unrecognized = (s.get("audit", {}).get("census", {})
                        .get("shell_like_unrecognized"))
        if unrecognized:
            # A shell-like tool the parser does not treat as a shell — the
            # PowerShell blind spot that corrupted the pilot audit. Surface
            # it loudly; the stored audit is not trustworthy until fixed.
            print(f"  WARNING: unrecognized shell-like tool(s) "
                  f"{unrecognized} - audit undercounts shell activity; "
                  f"update casa.transcript.SHELL_TOOLS before analysis.",
                  flush=True)
        if is_infra_failure(s.get("cli", {})):
            # Every subsequent session would fail identically; keep the
            # partial batch resumable instead of burning through it.
            (out_dir / f"session-{i:02d}.json").unlink(missing_ok=True)
            print("ABORT: infrastructure failure (expired auth or usage "
                  "limit) - resolve, then re-run to resume: "
                  f"{s.get('cli', {}).get('result', '')[:120]}", file=sys.stderr)
            aborted = True
            break
        if args.sleep_s and pos < len(todo) - 1:
            time.sleep(args.sleep_s)

    summary = _write_summary(out_dir, args.sessions)
    print(f"{'aborted' if aborted else 'done'}: "
          f"{summary['successes']}/{summary['n']} recorded sessions succeeded "
          f"-> {out_dir}")
    return 2 if aborted else 0


if __name__ == "__main__":
    sys.exit(main())
