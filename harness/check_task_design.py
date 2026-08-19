#!/usr/bin/env python3
"""pre-commit 검사: 새 과제는 설계 검문을 통과해야 한다.

`pilot/tasks/<name>/`에 새 과제를 만들면 같은 디렉토리에 `DESIGN.md`가
있어야 하고, `harness/TASK_DESIGN_RUBRIC.md`의 일곱 항목을 전부 답해야
한다. 빈 항목이나 TODO/TBD가 남아 있으면 거부한다.

이 검사가 있는 이유: 이 프로젝트는 방향을 두 번 틀었는데 두 번 다 대체
과제가 결국 "함수 하나가 비어 있고 명세는 완전하다"로 되돌아갔다. 그러면
유저가 능력 차이로 체감하는 차원(판단·상충·정합·애매함·길이)이 설계에서
전부 탈락한다.

기존 11개 과제는 `harness/legacy_tasks.txt`로 면제한다 — 소급 적용을 피하기
위한 것이지 승인이 아니다.

비상 우회: CASA_SKIP_TASK_DESIGN=1
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gates import REPO  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

REQUIRED_SECTIONS = [
    (1, "판단 단계"),
    (2, "상충 요구"),
    (3, "기존 상태와의 정합"),
    (4, "애매함"),
    (5, "길이와 규율"),
    (6, "채점 환원"),
    (7, "기술적 실패 분리"),
]
PLACEHOLDER = re.compile(r"\b(TODO|TBD|FIXME|작성\s*예정|미작성)\b", re.IGNORECASE)


def load_legacy(path: Path) -> set[str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return set()
    return {
        line.strip()
        for line in lines
        if line.strip() and not line.lstrip().startswith("#")
    }


def _sections(text: str) -> dict[int, str]:
    """'## 1. 제목' 형태로 나뉜 본문을 번호별로 모은다."""
    out: dict[int, str] = {}
    current: int | None = None
    buf: list[str] = []
    for line in text.splitlines():
        m = re.match(r"^#{1,6}\s*(\d+)\s*[.)]", line)
        if m:
            if current is not None:
                out[current] = "\n".join(buf)
            current = int(m.group(1))
            buf = []
        elif current is not None:
            buf.append(line)
    if current is not None:
        out[current] = "\n".join(buf)
    return out


def check_design(text: str) -> list[str]:
    """DESIGN.md 본문의 문제 목록. 빈 리스트면 통과."""
    problems: list[str] = []
    sections = _sections(text)
    for number, title in REQUIRED_SECTIONS:
        body = sections.get(number)
        if body is None:
            problems.append(f"{number}. {title} — 항목이 없다")
            continue
        stripped = "\n".join(
            line for line in body.splitlines() if line.strip()
        ).strip()
        if len(stripped) < 20:
            problems.append(f"{number}. {title} — 답이 비어 있다")
        elif PLACEHOLDER.search(stripped):
            problems.append(f"{number}. {title} — TODO/TBD가 남아 있다")
    return problems


def audit_tasks(tasks_root: Path, legacy: set[str]) -> dict[str, list[str]]:
    """면제 대상이 아닌 과제별 문제 목록."""
    findings: dict[str, list[str]] = {}
    if not tasks_root.is_dir():
        return findings
    for task in sorted(tasks_root.iterdir()):
        if not task.is_dir() or task.name in legacy:
            continue
        design = task / "DESIGN.md"
        if not design.is_file():
            findings[task.name] = ["DESIGN.md가 없다"]
            continue
        try:
            problems = check_design(design.read_text(encoding="utf-8"))
        except OSError as exc:
            problems = [f"DESIGN.md를 읽지 못했다: {exc}"]
        if problems:
            findings[task.name] = problems
    return findings


def main() -> int:
    if os.environ.get("CASA_SKIP_TASK_DESIGN"):
        return 0
    legacy = load_legacy(REPO / "harness" / "legacy_tasks.txt")
    findings = audit_tasks(REPO / "pilot" / "tasks", legacy)
    if not findings:
        return 0
    sys.stderr.write("pre-commit: 새 과제가 설계 검문을 통과하지 못했다.\n")
    for task, problems in findings.items():
        sys.stderr.write(f"  pilot/tasks/{task}/DESIGN.md\n")
        for p in problems:
            sys.stderr.write(f"    - {p}\n")
    sys.stderr.write(
        "  루브릭: harness/TASK_DESIGN_RUBRIC.md\n"
        "  특히 6번(채점 환원)이 핵심이다 — 두 해석이 서로 다른 검사 가능한 "
        "산출물을 낳는가.\n"
        "  우회(권장하지 않음): CASA_SKIP_TASK_DESIGN=1 git commit ...\n"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
