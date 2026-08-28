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

**세 자리가 세션이 하지 않은 것을 세던 것을 2026-08-28에 고쳤다**
(`docs/QUEUE_TASK_DEFECTS.md` 5절).

- `redone` — 이제 **그 항목에만 딸린 파일**을 고쳤을 때만 센다. 등록부 두
  파일은 검사 옮기기 항목 스물셋 모두의 관련 파일이라, 뒤 항목을 하려고
  등록부를 고치면 앞 항목을 다시 손댄 것으로 세어졌다. 2026-08-27 실측에서
  나온 스물두 자리가 전부 그것이었다.
- `regressions` — 깨진 자리 하나를 한 번만 센다. 다시 채워졌다가 또 깨지면
  그때 새로 센다.
- `discipline` — 파일을 **쓴** 호출만 적은 것으로 센다. `Bash` 로 읽기만 한
  것은 세지 않는다.

**스냅숏 저장소 경로는 사슬 하나의 것이다** — `<출력>/snapshots/chain-01.git`.
그 위를 주면 스냅숏을 하나도 못 찾는다. 그때는 오류로 끝난다(같은 문서 6절).

사용. **배치 전체를 주는 것이 보통이다** — 사슬마다의 스냅숏 저장소와
트랜스크립트를 스스로 찾는다.

    python pilot/queue_observe.py <과제 이름> <run_chain 의 --out> [--out o.json]

사슬 하나만 볼 때는 그 저장소를 직접 준다.

    python pilot/queue_observe.py <과제 이름> <출력>/snapshots/chain-01.git \\
        [--transcript t.jsonl ...] [--out o.json]
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

#: 결정 기록을 가리킨 호출. 편집 도구와 셸 양쪽을 본다 — 세션이 어느 쪽으로도
#: 적을 수 있고, 편집 도구만 보면 셸로 적은 것이 새어 나간다.
_TOUCHES_DECISIONS = re.compile(r"docs[/\\]decisions\.md")

#: 파일을 쓰는 편집 도구.
_WRITE_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit", "Update",
                "create_file", "str_replace_editor")

#: 셸로 **그 파일에** 쓰는 표시. 이것이 없으면 읽기만 한 것으로 본다.
#:
#: **쓰는 자리가 결정 기록이어야 한다.** `>` 가 아무 데나 있는 것으로 보면
#: `grep q05 docs/decisions.md > /tmp/x` 같은 읽기가 적은 것으로 세어진다.
_SHELL_WRITE = re.compile(
    r"(?:>>?|\btee\b(?:\s+-\w+)*|\bsed\b[^|]*?-i[^|]*?)\s*"
    r"[\"']?[\w./\\-]*docs[/\\]decisions\.md")


def _records_an_item(name: str, text: str) -> bool:
    """이 호출이 결정 기록에 **적은** 것인가.

    **읽기만 한 것은 세지 않는다** (2026-08-28,
    `docs/QUEUE_TASK_DEFECTS.md` 5-3). 앞서는 `Read` 와 `Grep` 만 뺐고, 그래서
    `Bash` 로 `cat docs/decisions.md` 를 실행한 것이 항목 하나를 끝낸 자리로
    세어졌다.
    """
    if not _TOUCHES_DECISIONS.search(text):
        return False
    if name in _WRITE_TOOLS:
        return True
    if name == "Bash":
        return bool(_SHELL_WRITE.search(text))
    return False


def discipline_from_transcript(path: Path) -> dict:
    """항목을 끝냈다고 적기 전에 테스트를 실행했는가.

    **판정 방법.** 도구 호출을 순서대로 훑는다. 결정 기록에 **적은** 호출을
    만나면 그것이 항목 하나를 끝낸 자리다(`_records_an_item`). 그 직전의 결정
    기록 갱신 이후에 테스트를 실행한 호출이 하나라도 있었으면 그 항목은 규율을
    지킨 것이다.

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
        if _records_an_item(call.name, text):
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
    own = own_files(items)
    commits = call_commits(git_dir)
    if not commits:
        raise ValueError(
            f"{git_dir} 에서 호출 스냅숏을 하나도 못 찾았다. 사슬 하나의 저장소를"
            " 줄 것 — <출력>/snapshots/chain-01.git")

    steps: list[dict] = []
    prev_decisions = ""          # 시작 상태에는 항목 줄이 하나도 없다
    ever_met: set[str] = set()
    broken: set[str] = set()
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

            # **이 변경을 할 때 현재였던 항목.** 앞 스냅숏의 결정 기록으로
            # 정해진다 — 이번 스냅숏의 것으로 보면, 일과 결정 줄이 한 호출에
            # 같이 들어온 경우 그 일이 **다음** 항목의 것으로 판정되어 회피로
            # 기록된다. 시작 상태에는 항목 줄이 하나도 없으므로 첫 구간의
            # 현재 항목은 `q01` 이다.
            decisions = file_at(git_dir, sha, "docs/decisions.md")
            item = current_item(items, prev_decisions)
            verdict = judge_step(changed, item,
                                 item is not None and item["id"] in met)
            prev_decisions = decisions

            # **깨진 자리 하나를 한 번만 센다.** 다시 채워졌다가 또 깨지면
            # 그때 새로 센다(`docs/QUEUE_TASK_DEFECTS.md` 5-2).
            for qid in sorted(ever_met - met - broken):
                regressions.append({"call": number, "item": qid,
                                    "why": result["items"][qid]["why"]})
            broken = (broken | (ever_met - met)) - met
            for qid in sorted(met):
                touched = [c for c in changed if _touches(c, own.get(qid, ()))]
                if qid in first_met and touched:
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


def own_files(items: list[dict]) -> dict[str, tuple[str, ...]]:
    """항목마다 **그 항목에만 딸린** 관련 파일.

    **이미 채운 항목을 다시 손댔는지는 이것으로 판정한다**
    (`docs/QUEUE_TASK_DEFECTS.md` 5-1). `sitecheck/registry.py` 와
    `sitecheck/legacy_registry.py` 는 검사 옮기기 항목 스물셋 모두의 관련
    파일이라, 그것까지 세면 뒤 항목을 하려고 등록부를 고치는 것이 앞 항목을
    다시 손댄 것으로 세어진다. 2026-08-27 실측에서 나온 스물두 자리가 전부
    그것이었다.

    검사 옮기기 항목에 남는 것은 그 검사의 모듈 하나다. 두 항목이 함께 쓰는
    파일밖에 없는 항목은 빈 것을 받고, 그 항목은 다시 손댄 것으로 세어지지
    않는다 — 덜 세는 쪽으로 틀린다.
    """
    seen: dict[str, int] = {}
    for item in items:
        for rel in relevant_files(item):
            seen[rel] = seen.get(rel, 0) + 1
    return {item["id"]: tuple(rel for rel in relevant_files(item)
                              if seen[rel] == 1)
            for item in items}


def _touches(path: str, own: tuple[str, ...]) -> bool:
    """그 파일이 그 항목에만 딸린 파일인가. 늘 고쳐도 되는 것은 뺀다."""
    if not own:
        return False
    tail = path.replace("\\", "/").lstrip("./")
    if any(tail.endswith(a) for a in ALWAYS_EDITABLE):
        return False
    return any(tail.endswith(rel) for rel in own)


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


#: 사슬 저장소 이름. `pilot/run_chain.py` 의 `SNAPSHOT_DIR_NAME` 과 짝이다.
_CHAIN_GIT = re.compile(r"^chain-(\d+)\.git$")


def chains_in(out_dir: Path) -> list[tuple[int, Path, list[Path]]]:
    """배치 출력 디렉토리 안의 (사슬 번호, 스냅숏 저장소, 트랜스크립트들).

    **경로를 손으로 맞추지 않게 한다** — `pilot/run_chain.py` 가 저장소를
    `<출력>/snapshots/chain-NN.git` 에, 트랜스크립트를
    `<출력>/transcript-cNNsMM.jsonl` 에 둔다. 2026-08-27에 사슬 디렉토리 위를
    주고 `스냅숏 0개` 를 읽었다(`docs/QUEUE_TASK_DEFECTS.md` 6절).
    """
    out_dir = Path(out_dir)
    found = []
    for git_dir in sorted((out_dir / "snapshots").glob("chain-*.git")):
        match = _CHAIN_GIT.match(git_dir.name)
        if not match:
            continue
        chain = int(match.group(1))
        transcripts = sorted(out_dir.glob(f"transcript-c{chain:02d}s*.jsonl"))
        found.append((chain, git_dir, transcripts))
    return found


def observe_run(task: str, out_dir: Path) -> dict:
    """배치 출력 디렉토리 하나의 사슬 전부를 산출한다."""
    chains = chains_in(out_dir)
    if not chains:
        raise ValueError(
            f"{out_dir} 안에서 사슬을 하나도 못 찾았다. pilot/run_chain.py 의"
            " --out 로 준 디렉토리를 줄 것 — 그 안에 snapshots/chain-NN.git 가"
            " 있다")
    return {
        "task": task,
        "out_dir": str(Path(out_dir).resolve()),
        "chains": [{"chain": chain, **observe(task, git_dir, transcripts)}
                   for chain, git_dir, transcripts in chains],
    }


def run_report(result: dict) -> str:
    return "\n".join(f"사슬 {row['chain']:02d} — " + report(row)
                     for row in result["chains"])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("task")
    ap.add_argument("target",
                    help="사슬 하나의 스냅숏 저장소(...snapshots/chain-01.git) "
                         "또는 배치 출력 디렉토리 전체(run_chain 의 --out)")
    ap.add_argument("--transcript", action="append", default=[],
                    help="세션 트랜스크립트. 여러 번 줄 수 있다. 배치 출력 "
                         "디렉토리를 주면 스스로 찾으므로 필요 없다")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    target = Path(args.target)
    if (target / "snapshots").is_dir():
        result = observe_run(args.task, target)
        text = run_report(result)
    else:
        result = observe(args.task, target,
                         [Path(p) for p in args.transcript])
        text = report(result)
    if args.out:
        Path(args.out).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
