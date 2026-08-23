#!/usr/bin/env python3
"""발견 시점이 다른 두 자리에서 **같은 결함을 고치는 값**을 잰다.

**왜 이 도구가 따로 있나**(`docs/REPAIR_COST_DESIGN.md`). 유저 지적
(2026-08-23): 거짓 완료 기록의 실제 값은 에이전트가 그것을 알아서 찾아내는
것이 아니라 **사람이 한참 뒤에 찾아내고 그때부터 치르는 값**이다. 그래서
재는 것을 "발견하는가" 에서 **"발견 뒤 고치는 값이 발견 시점에 따라 얼마나
다른가"** 로 바꾼다.

**사람은 발견 시각으로만 들어온다.** 어떤 눈으로 알아챘는지는 값에 안
들어가므로 모사하지 않는다. 발견자 자리는 채점기가 이미 맡고 있다 — 숨은
표본으로, 세션이 못 보는 것으로, 나중에 판정한다.

**시작 상태를 스냅숏에서 꺼내 쓴다.** 사슬 프로브가 남긴 스냅숏 저장소에서
두 시점의 작업 트리를 꺼내 각각 수리 세션을 붙인다. 결함은 같고 그 위에
쌓인 양만 다르다.

**수리 세션에는 증상만 준다**(`pilot/tasks/record-shape/repair_prompt.txt`).
어느 파일이 문제인지도, 어떻게 고치는지도 안 준다 — 실제 버그 보고가 증상을
적는다는 점에서 현실성 기준에 맞고, 앵커의 프롬프트 규칙 안쪽이다.

사용:

    python pilot/repair_run.py pilot/tasks/record-shape \\
        --snapshots results/probe/record-shape-chain/snapshots/chain-01.git \\
        --at early:<sha> --at late:<sha> --repeats 5 \\
        --out results/repair/record-shape
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import chain_budget  # noqa: E402
import run_sessions  # noqa: E402
import snapshot  # noqa: E402

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

PROMPT_NAME = "repair_prompt.txt"


def _git_env() -> dict:
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def materialize(git_dir: Path, sha: str, dest: Path) -> Path:
    """스냅숏 저장소의 그 시점 작업 트리를 `dest` 에 푼다.

    **`.venv/` 는 빼고 푼다.** 세션이 만든 가상 환경이 스냅숏에 통째로
    들어가 있어, 그대로 풀면 수리 세션이 남의 가상 환경을 물려받는다.
    """
    dest = Path(dest)
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True)
    done = subprocess.run(
        ["git", f"--git-dir={git_dir}", "archive", sha],
        capture_output=True, env=_git_env())
    if done.returncode != 0:
        raise SystemExit(f"그 시점을 못 꺼냈다: {sha}")
    unpack = subprocess.run(["tar", "-x", "-C", str(dest)],
                            input=done.stdout, capture_output=True)
    if unpack.returncode != 0:
        raise SystemExit(f"작업 트리를 못 풀었다: {unpack.stderr[:200]!r}")
    shutil.rmtree(dest / ".venv", ignore_errors=True)
    return dest


def prepare(git_dir: Path, sha: str, dest: Path) -> Path:
    """그 시점 트리를 풀고 세션이 쓸 git 저장소로 만든다."""
    materialize(git_dir, sha, dest)
    run = lambda *cmd: subprocess.run(cmd, cwd=dest, check=True,
                                      capture_output=True, env=_git_env())
    run("git", "init", "-q", "-b", "main")
    run("git", "-c", "user.name=pilot", "-c", "user.email=pilot@casa.local",
        "add", "-A")
    run("git", "-c", "user.name=pilot", "-c", "user.email=pilot@casa.local",
        "commit", "-q", "-m", "state at discovery")
    return dest


def grade(task_dir: Path, work_dir: Path) -> dict:
    try:
        done = subprocess.run(
            [sys.executable, str(task_dir / "grade.py"), str(work_dir)],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=600)
        return json.loads(done.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, TypeError,
            OSError) as exc:
        return {"parse_error": True, "detail": str(exc)[:300]}


def repaired(before: dict, after: dict,
             targets: list[str] | None = None) -> dict:
    """수리 목표가 채워졌는가, 그리고 다른 것을 깨뜨렸는가.

    **목표를 밖에서 준다.** 시작 시점에 안 통과하는 항목을 전부 목표로 삼으면
    이른 시점에서는 아직 안 만든 릴리스 전체가 목표가 되어 두 자리를 견줄 수
    없다. 같은 결함 하나를 두 자리에서 똑같이 지목해야 한다.

    **고쳤는가와 깨뜨렸는가를 같이 낸다.** 호출을 적게 쓰고 끝났는데 다른
    항목을 떨어뜨렸다면 싸게 고친 것이 아니다.
    """
    start = (before or {}).get("checkpoints") or {}
    end = (after or {}).get("checkpoints") or {}
    if targets is None:
        target = sorted(name for name, value in start.items()
                        if value is not True)
    else:
        target = sorted(targets)
    fixed = sorted(name for name in target if end.get(name) is True)
    broke = sorted(name for name, value in start.items()
                   if value is True and end.get(name) is not True)
    return {"target": target, "fixed": fixed, "broke": broke,
            "target_n": len(target), "fixed_n": len(fixed),
            "broke_n": len(broke)}


def run_one(task_dir: Path, git_dir: Path, sha: str, out_dir: Path,
            label: str, budget: int, timeout_s: int,
            model: str | None, targets: list[str] | None = None) -> dict:
    work = out_dir / f"work-{label}"
    prepare(git_dir, sha, work)
    before = grade(task_dir, work)

    # 예산 훅 다음에 스냅숏 훅을 배선한다. 순서가 바뀌면 스냅숏이 조용히
    # 빠진다 — 사슬 러너와 같은 순서를 지킨다.
    chain_budget.install(work, budget)
    snapshot.install(work, out_dir / "snapshots" / f"{label}.git")
    prompt = (task_dir / PROMPT_NAME).read_text(encoding="utf-8")
    started = time.time()
    cli = run_sessions.run_headless(work, prompt, model, timeout_s)
    snapshot.take(work)
    after = grade(task_dir, work)

    row = {
        "task": task_dir.name, "label": label, "at": sha,
        "wall_s": round(time.time() - started, 1),
        "budget": budget, "cli": cli,
        "timed_out": bool(cli.get("timed_out")),
        "before": before, "after": after,
        "outcome": repaired(before, after, targets),
    }
    (out_dir / f"repair-{label}.json").write_text(
        json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
    return row


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task_dir")
    parser.add_argument("--snapshots", required=True,
                        help="사슬 프로브가 남긴 스냅숏 저장소")
    parser.add_argument("--at", action="append", default=[], required=True,
                        help="발견 시점. `이름:커밋` 꼴로 여러 번 준다")
    parser.add_argument("--repeats", type=int, default=5,
                        help="자리마다 몇 번 되풀이하는가")
    parser.add_argument("--budget", type=int, default=100)
    parser.add_argument("--timeout-min", type=int, default=40)
    parser.add_argument("--model", default=None)
    parser.add_argument("--target", action="append", default=[],
                        help="수리 목표로 삼을 달성 항목 이름. 여러 번 준다. "
                             "안 주면 시작 시점에 안 통과하는 것을 다 삼는다 "
                             "— 두 자리를 견줄 때는 반드시 준다.")
    parser.add_argument("--out", default="results/repair")
    args = parser.parse_args(argv)

    task_dir = Path(args.task_dir).resolve()
    git_dir = Path(args.snapshots).resolve()
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    points = []
    for entry in args.at:
        name, _, sha = entry.partition(":")
        if not name or not sha:
            parser.error(f"`이름:커밋` 꼴이어야 한다: {entry}")
        points.append((name, sha))

    (out_dir / "meta.json").write_text(json.dumps({
        "task": task_dir.name, "snapshots": str(git_dir),
        "points": points, "repeats": args.repeats,
        "targets": args.target,
        "budget": args.budget, "model": args.model,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    rows = []
    for name, sha in points:
        for index in range(1, args.repeats + 1):
            label = f"{name}-{index:02d}"
            if (out_dir / f"repair-{label}.json").exists():
                continue                      # 이어 돌리기
            row = run_one(task_dir, git_dir, sha, out_dir, label,
                          args.budget, args.timeout_min * 60, args.model,
                          args.target or None)
            rows.append(row)
            got = row["outcome"]
            calls = ((row.get("cli") or {}).get("num_turns") or 0)
            print(f"  {label}  {row['wall_s']:>6.1f}s  "
                  f"고침 {got['fixed_n']}/{got['target_n']}  "
                  f"깨뜨림 {got['broke_n']}  turns {calls}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
