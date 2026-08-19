#!/usr/bin/env python3
"""pre-commit 검사: 기록 누락을 막는다.

두 가지를 본다.

1. **상태 기록 동반** — 코드·과제·훅·규칙을 건드린 커밋에는 `STATUS.md`가
   같이 들어 있어야 한다 (CLAUDE.md의 세션 인수인계 규칙).
2. **미기록 수집 배치** — `results/` 아래 배치 디렉토리 중 `STATUS.md`가
   한 번도 언급하지 않은 것이 있으면 거부한다.

2번이 있는 이유: `results/main2/ml-shift-sonnet`의 7세션이 상태 기록에 없는
채로 3주 넘게 남아 있었고, 다음 세션이 우연히 발견했다. 발견 여부가 세션마다
갈리는 종류의 일은 사람에게 맡기면 안 된다.

비상 우회: CASA_SKIP_STATUS_CHECK=1 / CASA_SKIP_RECORD_CHECK=1
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gates import REPO  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

# 이 경로들이 바뀌면 작업 상태가 바뀐 것으로 본다.
WORK_PREFIXES = ("src/", "pilot/", "hooks/", "rules/", "harness/")
STATUS = "STATUS.md"


def needs_status(staged: list[str]) -> bool:
    """작업 경로를 건드렸는데 STATUS.md가 빠졌는가."""
    touched = [p for p in staged if p.startswith(WORK_PREFIXES)]
    return bool(touched) and STATUS not in staged


def unrecorded_batches(results_root: Path, status_text: str) -> list[str]:
    """STATUS.md가 언급하지 않는 수집 배치 디렉토리 목록."""
    if not results_root.is_dir():
        return []
    missing: list[str] = []
    for group in sorted(results_root.iterdir()):
        if not group.is_dir():
            continue
        for batch in sorted(group.iterdir()):
            if not batch.is_dir():
                continue
            if batch.name not in status_text:
                missing.append(f"{group.name}/{batch.name}")
    return missing


def _staged_files() -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        check=False,
    )
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


def main() -> int:
    failed = False

    if not os.environ.get("CASA_SKIP_STATUS_CHECK"):
        staged = _staged_files()
        if needs_status(staged):
            sys.stderr.write(
                "pre-commit: 코드/과제/훅/규칙을 바꿨는데 STATUS.md가 같은 커밋에 "
                "없다 (CLAUDE.md: 작업 상태가 바뀌면 같은 커밋에서 갱신).\n"
                "  무엇이 어떻게 바뀌었는지 STATUS.md에 적고 다시 커밋할 것.\n"
                "  우회(권장하지 않음): CASA_SKIP_STATUS_CHECK=1 git commit ...\n"
            )
            failed = True

    if not os.environ.get("CASA_SKIP_RECORD_CHECK"):
        try:
            status_text = (REPO / STATUS).read_text(encoding="utf-8")
        except OSError:
            status_text = ""
        missing = unrecorded_batches(REPO / "results", status_text)
        if missing:
            sys.stderr.write(
                "pre-commit: STATUS.md에 기록되지 않은 수집 배치가 있다:\n"
            )
            for name in missing:
                sys.stderr.write(f"  - results/{name}\n")
            sys.stderr.write(
                "  각 배치의 조건(과제·모델·세션 수)과 결과를 STATUS.md에 적을 것.\n"
                "  우회(권장하지 않음): CASA_SKIP_RECORD_CHECK=1 git commit ...\n"
            )
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
