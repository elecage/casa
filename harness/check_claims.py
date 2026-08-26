#!/usr/bin/env python3
"""pre-commit 검사: 이미 틀린 것으로 확인된 사실 주장이 저장소에 다시 들어오는 것을 막는다.

목록과 판정 방법은 `harness/claim_check.py` 와 같은 것을 쓴다. 그쪽은 세션이
유저에게 보내는 답을 보고, 이쪽은 저장소의 파일을 본다. 2026-08-26에 실제로
일어난 경로가 그 둘이었다 — 틀린 문장이 파일 여섯에 적혀 있었고, 세션이 그것을
읽어 유저에게 인용했다.

두 가지로 나눠 본다.

1. **보통 파일** — 전문을 본다. `.md`, `.txt`, `.py` 중 git 이 추적하는 것.
2. **기록 파일** (`claim_rules.json` 의 `history_files`, 지금은 `STATUS.md`) —
   **이번 커밋에서 새로 더한 줄만** 본다. 날짜가 붙은 기록의 지난 항목은 그때
   그렇게 적었다는 사실 자체가 기록이므로 고쳐 쓰지 않는다.

비상 우회: CASA_SKIP_CLAIM_CHECK=1
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from claim_check import (  # noqa: E402
    build_message,
    find_false_claims,
    load_history_files,
    load_rules,
)
from gates import REPO  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

TEXT_SUFFIXES = (".md", ".txt", ".py")

#: 보지 않는 경로.
#:
#: - `results*` 와 과제 저장소의 내용물 — 우리가 쓰는 글이 아니라 실험 자료다.
#: - `tests/` — **시험은 틀린 문장을 그대로 담고 있어야 한다.** 검사가 실제로
#:   그 문장을 잡는지 확인하려면 시험 자료에 그 문장이 있어야 하므로, 여기를
#:   검사하면 검사를 검증하는 시험이 검사에 막힌다(이 검사의 첫 실행에서 실제로
#:   그렇게 됐다). 대신 시험 쪽 문장이 문서로 새는 것은 `tests/` 밖을 보는 이
#:   검사가 막는다.
SKIP_PREFIXES = ("results", "tests/")
SKIP_PARTS = ("template", "solution", "__pycache__", ".venv")


def is_scanned(name: str) -> bool:
    """이 경로를 전문 검사 대상으로 보는가."""
    if not name.endswith(TEXT_SUFFIXES):
        return False
    if name.startswith(SKIP_PREFIXES):
        return False
    return not any(part in SKIP_PARTS for part in name.split("/"))


def tracked_files(repo: Path) -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(repo), "ls-files"],
        capture_output=True,
        text=True,
        check=False,
    )
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


def staged_additions(repo: Path, name: str) -> str:
    """이번 커밋에서 그 파일에 새로 더한 줄들.

    한 덩어리로 이어 붙여 한 문단처럼 대조한다 — 새로 더한 줄들은 대개 한
    문단이고, 문단 경계를 diff 로 복원하려 들면 판정이 diff 의 맥락 줄 수에
    딸려 간다.
    """
    out = subprocess.run(
        ["git", "-C", str(repo), "diff", "--cached", "-U0", "--", name],
        capture_output=True,
        text=True,
        check=False,
    )
    added = [
        line[1:]
        for line in out.stdout.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]
    return "\n".join(added)


def scan(files: dict[str, str], rules: list[dict] | None = None) -> dict[str, list[dict]]:
    """파일 이름 -> 검출된 항목들. 빈 사전이면 통과."""
    rules = load_rules() if rules is None else rules
    findings: dict[str, list[dict]] = {}
    for name, text in files.items():
        hits = find_false_claims(text, rules)
        if hits:
            findings[name] = hits
    return findings


def collect(repo: Path) -> dict[str, str]:
    """검사할 이름 -> 본문. 기록 파일은 새로 더한 줄만 담는다."""
    history = set(load_history_files())
    files: dict[str, str] = {}
    for name in tracked_files(repo):
        if name in history:
            added = staged_additions(repo, name)
            if added.strip():
                files[name] = added
            continue
        if not is_scanned(name):
            continue
        try:
            files[name] = (repo / name).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
    return files


def main() -> int:
    if os.environ.get("CASA_SKIP_CLAIM_CHECK"):
        return 0
    findings = scan(collect(REPO))
    if not findings:
        return 0
    sys.stderr.write(
        "pre-commit: 이미 틀린 것으로 확인된 주장이 파일에 들어 있다.\n"
    )
    for name, hits in findings.items():
        sys.stderr.write(f"  {name}\n")
        for line in build_message(hits, where="이 파일").splitlines()[1:]:
            sys.stderr.write(f"  {line}\n")
    sys.stderr.write(
        "  우회(권장하지 않음): CASA_SKIP_CLAIM_CHECK=1 git commit ...\n"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
