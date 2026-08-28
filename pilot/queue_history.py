#!/usr/bin/env python3
"""사슬이 남긴 호출별 스냅숏을 순서대로 채점한다.

**왜 따로 있나.** `pilot/run_chain.py` 는 세션이 끝날 때마다 한 번 채점한다.
그것으로는 **한 번 채워졌던 완료 조건이 나중에 안 채워지는 자리**가 안 잡힌다 —
세션 안에서 채웠다가 같은 세션 안에서 깨뜨리면 끝 상태만 보고는 구분되지 않는다
(`pilot/tasks/queue-flat/DESIGN.md` 6절). `pilot/queue_grade.py` 의
`grade_history` 가 그것을 세고, 이 파일이 스냅숏을 그것에 넣어 준다.

**주는 경로는 사슬 하나의 스냅숏 저장소다** — `<출력>/snapshots/chain-01.git`.
그 위(`<출력>/snapshots`)를 주면 커밋을 하나도 못 찾고 0을 돌려주며 정상
종료한다(`docs/QUEUE_TASK_DEFECTS.md` 6절).

**실행 중에 부르지 않는다.** 스냅숏 하나마다 저장소를 별도 프로세스로 불러
읽으므로 호출 수백 개면 오래 걸린다. 배치가 끝난 뒤에 따로 실행한다.

사용:

    python pilot/queue_history.py <과제 이름> <스냅숏 저장소.git> [--out 파일]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from queue_grade import grade_history  # noqa: E402

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

#: 스냅숏 훅이 붙이는 이름표. `pilot/snapshot.py` 가 `call N` 으로 커밋한다.
_CALL = re.compile(r"^call (\d+)$")


def _git_env() -> dict[str, str]:
    """부모 git 이 물려준 것을 뺀 환경.

    커밋 훅 안에서 돌면 `GIT_DIR`·`GIT_INDEX_FILE` 이 물려 내려와 엉뚱한
    저장소를 가리킨다. `pilot/snapshot.py` 가 같은 이유로 같은 것을 한다.
    """
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def call_commits(git_dir: Path) -> list[tuple[int, str]]:
    """(호출 번호, 커밋 해시) 목록. 호출 번호 순서다.

    `baseline` 커밋은 빼고 본다 — 세션이 시작하기 전 상태라 호출이 아니다.
    """
    done = subprocess.run(
        ["git", f"--git-dir={Path(git_dir).resolve()}", "log",
         "--format=%H %s", "--reverse"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=_git_env(), check=False)
    out: list[tuple[int, str]] = []
    for line in done.stdout.splitlines():
        sha, _, subject = line.partition(" ")
        match = _CALL.match(subject.strip())
        if match:
            out.append((int(match.group(1)), sha))
    return sorted(out)


def _checkout(git_dir: Path, sha: str, tree: Path, index: Path) -> bool:
    """그 커밋의 트리를 `tree` 에 펼친다. 성공했으면 참.

    색인을 임시 파일에 둔다 — 스냅숏 저장소의 색인을 건드리면 나중에 그
    저장소로 다시 스냅숏을 찍을 때 어긋난다.
    """
    env = {**_git_env(), "GIT_INDEX_FILE": str(index)}
    done = subprocess.run(
        ["git", f"--git-dir={Path(git_dir).resolve()}",
         f"--work-tree={tree}", "checkout", "-f", sha, "--", "."],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, check=False)
    return done.returncode == 0


def _trees(git_dir: Path, commits: list[tuple[int, str]],
           tree: Path, index: Path) -> Iterator[Path]:
    """스냅숏마다 트리를 **같은 자리에** 펼쳐 내놓는다.

    `grade_history` 는 받은 것을 순서대로 하나씩 채점하므로, 다음 것을 달라고
    할 때는 앞의 것을 이미 다 읽은 뒤다. 그래서 자리 하나를 다시 쓰는 것이
    안전하고, 호출 수백 개 분량의 트리를 동시에 펼치지 않아도 된다.
    """
    for _, sha in commits:
        if _checkout(git_dir, sha, tree, index):
            yield tree


def grade_chain(task: str, git_dir: Path) -> dict:
    """사슬 하나의 스냅숏 전부를 채점한다.

    **호출 스냅숏이 하나도 없으면 오류로 끝낸다.** 0을 돌려주면 한 번도
    실행되지 않은 채점과 구분되지 않는다 — 2026-08-27에 사슬 디렉토리 위를
    주고 `스냅숏 0개` 를 읽었다(`docs/QUEUE_TASK_DEFECTS.md` 6절).
    """
    commits = call_commits(git_dir)
    if not commits:
        raise ValueError(
            f"{git_dir} 에서 호출 스냅숏을 하나도 못 찾았다. 사슬 하나의 저장소를"
            " 줄 것 — <출력>/snapshots/chain-01.git")
    with tempfile.TemporaryDirectory(prefix="casa-history-") as tmp:
        tree = Path(tmp) / "tree"
        tree.mkdir()
        index = Path(tmp) / "index"
        result = grade_history(task, _trees(git_dir, commits, tree, index))
    result["calls"] = [number for number, _ in commits]
    result["git_dir"] = str(Path(git_dir).resolve())
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("task")
    ap.add_argument("git_dir")
    ap.add_argument("--out", default=None,
                    help="결과를 쓸 JSON 파일. 없으면 요약만 찍는다")
    args = ap.parse_args(argv)

    result = grade_chain(args.task, Path(args.git_dir))
    if args.out:
        Path(args.out).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{result['task']}: 스냅숏 {result['snapshots']}개, "
          f"끝에서 충족 {result['met_at_end']}개, "
          f"채웠다 깨진 자리 {len(result['regressions'])}개")
    for row in result["regressions"][:20]:
        print(f"  스냅숏 {row['at']}에서 {row['item']} 가 다시 안 채워짐: "
              f"{row['why']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
