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

from casa.audit import audit_session  # noqa: E402
from casa.rules import load_rules  # noqa: E402

CANARY_RULES = REPO / "rules" / "canary_rules.yaml"


def rules_for(task_dir: Path) -> Path:
    """Task-local canary_rules.yaml (task-specific refinements, e.g. the
    concretized search-before-write prerequisite) wins over the default."""
    local = task_dir / "canary_rules.yaml"
    return local if local.exists() else CANARY_RULES


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


def prepare_workdir(task_dir: Path, dest: Path) -> Path:
    """Copy the task template (never solution/ etc.) and make it a git repo
    with an initial commit, so the session can follow 'commit your changes'.
    An existing dest (leftover of a crashed session) is wiped first."""
    if dest.exists():
        _rmtree_force(dest)
    shutil.copytree(task_dir / "template", dest)
    run = lambda *cmd: subprocess.run(cmd, cwd=dest, check=True, capture_output=True)
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
    return env


def run_headless(workdir: Path, prompt: str, model: str | None,
                 timeout_s: int) -> dict:
    # The prompt goes through stdin, never the command line: on Windows the
    # command runs via the shell (npm .cmd shim), and cmd.exe mangles
    # multi-line arguments. The command string itself carries flags only.
    cmd = "claude -p --output-format json --dangerously-skip-permissions"
    if model:
        cmd += f" --model {model}"
    proc = subprocess.run(cmd, cwd=workdir, input=prompt,
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace",
                          timeout=timeout_s, env=_child_env(), shell=True)
    try:
        payload = json.loads(proc.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        payload = {"parse_error": True, "stdout_tail": proc.stdout[-1000:],
                   "stderr_tail": proc.stderr[-1000:]}
    payload["exit_code"] = proc.returncode
    return payload


def run_one(task_dir: Path, out_dir: Path, index: int, model: str | None,
            timeout_s: int) -> dict:
    prompt = (task_dir / "prompt.txt").read_text(encoding="utf-8")
    relevant = [ln.strip() for ln in
                (task_dir / "relevant_files.txt").read_text(encoding="utf-8").splitlines()
                if ln.strip()]
    workdir = prepare_workdir(task_dir, out_dir / f"work-{index:02d}")

    t0 = time.time()
    cli = run_headless(workdir, prompt, model, timeout_s)
    wall_s = round(time.time() - t0, 1)

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
        summary["audit"] = audit_session(saved, rules=load_rules(rules_for(task_dir)),
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
    (out_dir / "meta.json").write_text(json.dumps({
        "claude_version": version, "task": task_dir.name,
        "sessions": args.sessions, "model": args.model, "account": email,
    }, indent=2), encoding="utf-8")

    todo = pending_indices(out_dir, args.sessions)
    skipped = args.sessions - len(todo)
    if skipped:
        print(f"resume: {skipped} session(s) already done, "
              f"{len(todo)} to run", flush=True)

    aborted = False
    for pos, i in enumerate(todo):
        print(f"[{i}/{args.sessions}] running...", flush=True)
        s = run_one(task_dir, out_dir, i, args.model, args.timeout_min * 60)
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
