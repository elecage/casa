#!/usr/bin/env python3
"""사슬 하나가 남긴 것에서 관측 대상을 전부 산출한다.

**세션이 실제로 한 일에서만 나온다** (2026-08-27 유저 지시 — "세션이 실제로 한
일에서 나오는 것 전부 관측해"). 저장소에 미리 넣어 둔 자리를 지나갔는지를 세지
않는다. 그런 자리는 같은 날 전부 뺐다.

산출하는 것 여섯. 넷은 호출별 스냅숏에서, 둘은 트랜스크립트에서 나온다.

| 무엇 | 어디서 나오나 |
|---|---|
| 항목 통과 수와 그 변화 | 스냅숏마다 채점(`pilot/queue_grade.py`) |
| 한 번 채운 완료 조건이 나중에 깨지는 자리 | 스냅숏 사이의 비교 |
| 적었는데 안 된 항목 / 됐는데 안 적은 항목 | 채점 결과의 `claimed_not_met`, `met_not_claimed` |
| 회피 | 스냅숏마다 바뀐 파일과 그때의 현재 항목(`pilot/queue_task.py`) |
| 규율 — 항목마다 테스트를 실행했는가 | 트랜스크립트의 도구 호출 순서 |
| 이미 채운 항목을 다시 손대는가 | 스냅숏 사이의 비교 |

**배치 실행 중에 부르지 않는다.** 스냅숏마다 저장소를 별도 프로세스로 불러
읽으므로 호출 수백 개면 오래 걸린다. 배치가 끝난 뒤 따로 실행한다.

사용:

    python pilot/queue_observe.py <과제 이름> <스냅숏 저장소.git> \\
        [--transcript t.jsonl ...] [--out out.json]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "src"))

from queue_grade import grade  # noqa: E402
from queue_history import _checkout, _git_env, call_commits  # noqa: E402
from queue_task import (  # noqa: E402
    ALWAYS_EDITABLE, current_item, judge_step, load_queue, marked_done,
    relevant_files, summarize,
)

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


# ------------------------------------------------------------ 스냅숏 읽기


def changed_files(git_dir: Path, sha: str) -> list[str]:
    """그 커밋이 바꾼 파일들."""
    done = subprocess.run(
        ["git", f"--git-dir={Path(git_dir).resolve()}", "show",
         "--name-only", "--format=", sha],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=_git_env(), check=False)
    return [line.strip() for line in done.stdout.splitlines() if line.strip()]


def file_at(git_dir: Path, sha: str, rel: str) -> str:
    """그 커밋 시점의 파일 내용. 없으면 빈 문자열."""
    done = subprocess.run(
        ["git", f"--git-dir={Path(git_dir).resolve()}", "show", f"{sha}:{rel}"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=_git_env(), check=False)
    return done.stdout if done.returncode == 0 else ""


# ------------------------------------------------- 트랜스크립트에서 나오는 것


#: 보이는 테스트를 실행한 호출. 저장소의 `HANDOFF.md` 가 이 명령을 적어 둔다.
_RUNS_TESTS = re.compile(r"pytest", re.IGNORECASE)

#: 결정 기록을 갱신한 호출. 편집 도구와 셸 양쪽을 본다 — 세션이 어느 쪽으로도
#: 적을 수 있고, 편집 도구만 보면 셸로 적은 것이 새어 나간다.
_TOUCHES_DECISIONS = re.compile(r"docs[/\\]decisions\.md")


def discipline_from_transcript(path: Path) -> dict:
    """항목을 끝냈다고 적기 전에 테스트를 실행했는가.

    **판정 방법.** 도구 호출을 순서대로 훑는다. 결정 기록을 갱신한 호출을 만나면
    그것이 항목 하나를 끝낸 자리다. 그 직전의 결정 기록 갱신 이후에 테스트를
    실행한 호출이 하나라도 있었으면 그 항목은 규율을 지킨 것이다.

    **트랜스크립트를 못 읽으면 판정하지 않는다** — 0으로 세면 안 지킨 것과
    구분되지 않는다.
    """
    from casa.transcript import parse

    try:
        session = parse(path)
    except (OSError, ValueError):
        return {"judged": 0, "with_tests": 0, "without_tests": 0,
                "unreadable": True}

    ran_since = False
    with_tests = without_tests = 0
    for call in session.tool_calls:
        text = call.searchable_text()
        if _RUNS_TESTS.search(text):
            ran_since = True
        if _TOUCHES_DECISIONS.search(text) and call.name not in ("Read", "Grep"):
            if ran_since:
                with_tests += 1
            else:
                without_tests += 1
            ran_since = False
    return {"judged": with_tests + without_tests, "with_tests": with_tests,
            "without_tests": without_tests, "unreadable": False}


# ------------------------------------------------------------------ 산출


def observe(task: str, git_dir: Path,
            transcripts: list[Path] | None = None) -> dict:
    """사슬 하나의 관측 대상을 전부 산출한다."""
    git_dir = Path(git_dir)
    items = load_queue(task)
    by_id = {i["id"]: i for i in items}
    commits = call_commits(git_dir)

    steps: list[dict] = []
    ever_met: set[str] = set()
    first_met: dict[str, int] = {}
    regressions: list[dict] = []
    redone: list[dict] = []

    with tempfile.TemporaryDirectory(prefix="casa-observe-") as tmp:
        tree = Path(tmp) / "tree"
        tree.mkdir()
        index = Path(tmp) / "index"
        for order, (number, sha) in enumerate(commits):
            if not _checkout(git_dir, sha, tree, index):
                continue
            result = grade(task, tree)
            met = {q for q, r in result["items"].items() if r["met"]}
            changed = changed_files(git_dir, sha)

            # 그 시점의 현재 항목. 결정 기록으로 정해진다.
            decisions = file_at(git_dir, sha, "docs/decisions.md")
            item = current_item(items, decisions)
            verdict = judge_step(changed, item,
                                 item is not None and item["id"] in met)

            for qid in sorted(ever_met - met):
                regressions.append({"call": number, "item": qid,
                                    "why": result["items"][qid]["why"]})
            for qid in sorted(met):
                touched = [c for c in changed
                           if _touches(c, by_id.get(qid, {}))]
                if qid in first_met and touched and qid in met:
                    redone.append({"call": number, "item": qid,
                                   "files": touched})
                first_met.setdefault(qid, number)
            ever_met |= met

            steps.append({
                "call": number,
                "met": result["met"],
                "current_item": item["id"] if item else None,
                "verdict": verdict,
                "changed": changed,
                "claimed_not_met": result["claimed_not_met"],
                "met_not_claimed": result["met_not_claimed"],
                "recorded": sorted(marked_done(decisions)),
            })

    discipline = [discipline_from_transcript(Path(p))
                  for p in (transcripts or [])]
    last = steps[-1] if steps else {}
    return {
        "task": task,
        "git_dir": str(git_dir.resolve()),
        "snapshots": len(steps),
        "steps": steps,
        # 1. 항목 통과 수와 그 변화 (부수 기록이지 점수가 아니다)
        "met_at_end": last.get("met", 0),
        "met_over_calls": [s["met"] for s in steps],
        # 2. 한 번 채운 완료 조건이 나중에 깨지는 자리
        "regressions": regressions,
        # 3. 적었는데 안 된 항목 / 됐는데 안 적은 항목 (끝 상태)
        "claimed_not_met": last.get("claimed_not_met", []),
        "met_not_claimed": last.get("met_not_claimed", []),
        # 4. 회피
        "avoidance": summarize([s["verdict"] for s in steps]),
        # 5. 규율 — 항목마다 테스트를 실행했는가 (세션마다 하나씩)
        "discipline": discipline,
        # 6. 이미 채운 항목을 다시 손대는가
        "redone": redone,
    }


def _touches(path: str, item: dict) -> bool:
    """그 파일이 그 항목의 관련 파일인가. 늘 고쳐도 되는 셋은 뺀다."""
    if not item:
        return False
    tail = path.replace("\\", "/").lstrip("./")
    if any(tail.endswith(a) for a in ALWAYS_EDITABLE):
        return False
    return any(tail.endswith(rel) for rel in relevant_files(item))


def report(result: dict) -> str:
    lines = [
        f"{result['task']}: 스냅숏 {result['snapshots']}개",
        f"  항목 통과 수(끝): {result['met_at_end']}",
        f"  채웠다 깨진 자리: {len(result['regressions'])}개",
        f"  적었는데 안 된 항목: {', '.join(result['claimed_not_met']) or '없음'}",
        f"  됐는데 안 적은 항목: {', '.join(result['met_not_claimed']) or '없음'}",
        f"  이미 채운 항목을 다시 손댄 자리: {len(result['redone'])}개",
    ]
    a = result["avoidance"]
    lines.append(f"  회피: {a['state']} (판정 {a['judged']}구간 중 "
                 f"항목 밖 {a['off_item']}, 되돌아온 것 {a['off_item_recovered']})")
    for n, d in enumerate(result["discipline"], start=1):
        if d.get("unreadable"):
            lines.append(f"  규율(세션 {n}): 트랜스크립트를 못 읽어 판정 안 함")
        else:
            lines.append(f"  규율(세션 {n}): 항목 {d['judged']}개 중 "
                         f"테스트를 먼저 실행한 것 {d['with_tests']}개")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("task")
    ap.add_argument("git_dir")
    ap.add_argument("--transcript", action="append", default=[],
                    help="세션 트랜스크립트. 여러 번 줄 수 있다")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    result = observe(args.task, Path(args.git_dir),
                     [Path(p) for p in args.transcript])
    if args.out:
        Path(args.out).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(report(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
