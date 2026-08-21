#!/usr/bin/env python3
"""Run a project as a chain of sessions (docs/MULTISESSION_ARM.md).

Difference from `run_sessions.py`, which runs independent sessions of one
task: here the sessions of a chain share one working directory. Session 2
starts from whatever session 1 left behind — the repo, the commits, and any
handoff note. That is the whole point: the phenomenon under study is what
happens *between* sessions, and a design with one session per task cannot
show it.

Three things this adds:

  workdir inheritance   the chain's directory is prepared once, at session 1
  a session budget      enforced by pilot/chain_budget.py as a PreToolUse
                        hook, because the CLI has no turn cap and because
                        where a session stops must not be chosen by the thing
                        being measured
  grading at every seam the task grader runs after each session, and the
                        result is written to disk but never shown to the
                        agent — a session must not learn its score

Chains are isolated from each other the same way independent sessions were:
separate directory, separate git repo, separate transcript project dir.
Inside a chain the sessions are deliberately dependent, so the unit of
analysis is the chain, not the session.

Usage:
    python pilot/run_chain.py pilot/tasks/casefile --chains 3 --sessions 6 \\
        --budget 60 --out results/chain/casefile
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from casa.audit import audit_session  # noqa: E402
from casa.rules import load_rules  # noqa: E402
import chain_budget  # noqa: E402
import snapshot  # noqa: E402
from run_sessions import (  # noqa: E402
    check_auth, prepare_workdir, rules_for, run_headless,
    session_never_started, transcript_dir_for,
)

HOOK = Path(__file__).resolve().parent / "chain_budget.py"
SNAPSHOT_DIR_NAME = "snapshots"
CONFIG_NAME = ".casa-chain.json"


def install_budget(workdir: Path, budget: int, warn_margin: int = 5) -> None:
    """예산 훅 배선. 구현은 `pilot/chain_budget.py` 에 있다 — 단발 러너도
    같은 것을 쓴다."""
    chain_budget.install(workdir, budget, warn_margin)


def grade(task_dir: Path, workdir: Path) -> dict:
    """Score the chain's current state. Never shown to the session."""
    try:
        done = subprocess.run(
            [sys.executable, str(task_dir / "grade.py"), str(workdir)],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=600)
        return json.loads(done.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, TypeError,
            OSError) as exc:
        # A session's own program can emit bytes that are not UTF-8; without
        # errors="replace" the reader thread dies and stdout comes back None,
        # which killed a whole chain mid-run. One ungradeable session must
        # never take the chain with it.
        return {"parse_error": True, "detail": str(exc)[:300]}


def collect_transcript(workdir: Path, cli: dict, out_dir: Path,
                       label: str, seen: set[str]) -> Path | None:
    """Copy this session's transcript out of the shared project directory.

    Chained sessions write into the same directory, so a transcript already
    claimed by an earlier session must not be picked up again.
    """
    tdir = transcript_dir_for(workdir)
    session_id = cli.get("session_id")
    candidate = tdir / f"{session_id}.jsonl" if session_id else None
    if candidate is None or not candidate.exists():
        if not tdir.exists():
            return None
        fresh = [p for p in tdir.glob("*.jsonl") if p.name not in seen]
        if not fresh:
            return None
        candidate = max(fresh, key=lambda p: p.stat().st_mtime)
    seen.add(candidate.name)
    saved = out_dir / f"transcript-{label}.jsonl"
    shutil.copyfile(candidate, saved)
    return saved


def completed_sessions(out_dir: Path, chain: int) -> int:
    """How far this chain already got, for resuming an interrupted batch.

    A chain is expensive and the usage window is finite; losing six sessions
    because the batch stopped at the fifth would be worse than the risk of
    continuing into a slightly odd state.
    """
    index = 0
    while (out_dir / f"session-c{chain:02d}s{index + 1:02d}.json").exists():
        index += 1
    return index


#: 둘째 세션부터 주는 프롬프트. 없으면 첫 세션 것을 그대로 쓴다.
FOLLOWUP_PROMPT = "prompt_followup.txt"


def load_prompts(task_dir: Path) -> tuple[str, str]:
    """(첫 세션 프롬프트, 후속 세션 프롬프트).

    **왜 갈라 주는가.** 사슬의 둘째 세션부터는 앞사람이 하던 일을 이어받는
    자리인데, 지금까지는 다섯 세션이 전부 "릴리스를 준비해라"라는 같은 말을
    받았다. 실제로 새 세션을 여는 사람은 "어제 하던 거 이어서" 라고 말한다.
    그 차이가 세션의 행동을 바꾸므로 조건에서 맞춰 준다.

    **프롬프트로 역량을 조절하는 것이 아니다**(`harness/anchor.md`). 실제
    사용자가 쓸 법한 말에 맞추는 것이고, 일하는 요령은 넣지 않는다.

    후속 프롬프트 파일이 없는 과제는 첫 세션 것을 그대로 쓴다 — 사슬이 아닌
    과제와 옛 과제 11종이 그렇다.
    """
    first = (task_dir / "prompt.txt").read_text(encoding="utf-8")
    followup = task_dir / FOLLOWUP_PROMPT
    if followup.is_file():
        return first, followup.read_text(encoding="utf-8")
    return first, first


def run_chain(task_dir: Path, out_dir: Path, chain: int, sessions: int,
              budget: int, model: str | None, timeout_s: int,
              resume: bool = False) -> list[dict]:
    first_prompt, next_prompt = load_prompts(task_dir)
    relevant = [ln.strip() for ln in
                (task_dir / "relevant_files.txt").read_text(
                    encoding="utf-8").splitlines() if ln.strip()]
    rules = load_rules(rules_for(task_dir))

    workdir = out_dir / f"chain-{chain:02d}"
    done = completed_sessions(out_dir, chain) if resume else 0
    if done and workdir.exists():
        print(f"  이어서 진행: 세션 {done}개 완료됨")
    else:
        # Prepared once, at session 1. Preparing it again would wipe the
        # previous session's work, which is the one thing a chain must keep.
        done = 0
        workdir = prepare_workdir(task_dir, workdir)
    install_budget(workdir, budget)
    # 예산 훅 다음에 배선한다 — settings.json 을 덮지 않고 합친다.
    snapshot.install(workdir, out_dir / SNAPSHOT_DIR_NAME /
                     f"chain-{chain:02d}.git")

    seen: set[str] = set()
    rows: list[dict] = []
    for index in range(done + 1, sessions + 1):
        label = f"c{chain:02d}s{index:02d}"
        started = time.time()
        cli = run_headless(workdir, first_prompt if index == 1 else next_prompt,
                           model, timeout_s)
        # 마지막 한 번 — 세션의 끝 편집을 훅이 못 잡고 끝나는 수가 있다.
        snapshot.take(workdir)
        row: dict = {
            "task": task_dir.name, "chain": chain, "session_index": index,
            "label": label, "wall_s": round(time.time() - started, 1),
            "cli": cli, "budget": budget,
        }

        transcript = collect_transcript(workdir, cli, out_dir, label, seen)
        row["transcript"] = str(transcript) if transcript else None
        if transcript:
            row["audit"] = audit_session(transcript, rules=rules,
                                         relevant_files=relevant)
        # Scored at the seam, kept from the session.
        row["grade"] = grade(task_dir, workdir)
        (out_dir / f"session-{label}.json").write_text(
            json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
        rows.append(row)

        score = row["grade"].get("milestone_score")
        print(f"  {label}  {row['wall_s']:>6.1f}s  마일스톤 {score}  "
              f"위반 {row['grade'].get('violations')}")

        # CLI가 아예 시작하지 못했으면 **배치를 멈춘다.** 다음 세션도 같은
        # 이유로 안 돌 것이고, 계속 돌리면 한 번도 실행되지 않은 세션 열 개가
        # 정상 완주로 기록된다. 2026-08-21에 실제로 그렇게 될 뻔했다 —
        # 컨테이너가 root라 CLI가 플래그를 거부했고, 다섯 세션이 각각 0.8초
        # 만에 끝났는데 러너는 넘어갔다.
        if session_never_started(cli):
            print(f"ABORT: {label} 에서 CLI 가 세션을 시작하지 못했다 — "
                  f"종료 코드 {cli.get('exit_code')}. "
                  f"stderr: {str(cli.get('stderr_tail', ''))[:300]}",
                  file=sys.stderr)
            raise SystemExit(3)
    return rows


def chain_summary(rows: list[dict]) -> dict:
    """Chain-level roll-up. The session is not the unit of analysis here."""
    scores = [r["grade"].get("milestone_score") for r in rows
              if isinstance(r["grade"].get("milestone_score"), int)]
    gains = [b - a for a, b in zip(scores, scores[1:])] if len(scores) > 1 else []
    final = rows[-1]["grade"] if rows else {}
    return {
        "sessions": len(rows),
        "final_milestone_score": final.get("milestone_score"),
        "final_violations": final.get("violations"),
        "per_session_scores": scores,
        "per_session_gain": gains,
        "stalled_sessions": sum(1 for g in gains if g <= 0),
        "total_wall_s": round(sum(r["wall_s"] for r in rows), 1),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("task_dir")
    ap.add_argument("--chains", type=int, default=1)
    ap.add_argument("--sessions", type=int, default=6)
    ap.add_argument("--budget", type=int, default=60,
                    help="tool calls per session")
    ap.add_argument("--out", default="results/chain")
    ap.add_argument("--model", default=None)
    ap.add_argument("--timeout-min", type=int, default=40)
    ap.add_argument("--resume", action="store_true",
                    help="continue chains that already have finished sessions")
    args = ap.parse_args(argv)

    task_dir = Path(args.task_dir).resolve()
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    logged_in, email = check_auth()
    if not logged_in:
        print("ABORT: claude CLI is not authenticated - run `claude auth login`",
              file=sys.stderr)
        return 2

    meta = {"task": task_dir.name, "chains": args.chains,
            "sessions_per_chain": args.sessions, "budget": args.budget,
            "model": args.model, "account": email}
    (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    summaries = []
    for chain in range(1, args.chains + 1):
        print(f"chain {chain}/{args.chains}")
        rows = run_chain(task_dir, out_dir, chain, args.sessions, args.budget,
                         args.model, args.timeout_min * 60, resume=args.resume)
        summary = chain_summary(rows)
        summaries.append(summary)
        print(f"  → 마일스톤 {summary['per_session_scores']} "
              f"진척 {summary['per_session_gain']}")

    (out_dir / "chains.json").write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
