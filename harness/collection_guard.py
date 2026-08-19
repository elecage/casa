#!/usr/bin/env python3
"""PreToolUse 훅: 잠겨 있는 동안 새 세션 수집 실행을 차단한다.

막는 것은 `pilot/run_sessions.py`의 **실행**뿐이다. 파일을 읽거나 고치는
것, 기존 데이터를 재분석하는 것은 막지 않는다 — 버그 수정과 재현은 계속
가능해야 하기 때문이다.

왜 코드로 막는가: 이 프로젝트의 설계 원칙이 "강제는 코드로, 프롬프트로
하지 않는다"이고, 실제로 문서에 적힌 규칙이 지켜지지 않은 이력이 있다.
"설계 문제를 측정으로 답하지 말 것"은 판단의 문제라 기계가 볼 수 없지만,
새 측정을 실행 못 하게 만들면 그 경로 자체가 닫힌다.

계약: stdin으로 {"tool_name":..., "tool_input":{...}} JSON. exit 2면 호출이
차단되고 stderr가 차단 사유로 모델에 전달된다. 그 외에는 exit 0.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gates import load_gates  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

SHELL_TOOLS = {"Bash", "PowerShell"}

_RUNNER = re.compile(r"run_sessions\.py")
_PYTHON = re.compile(r"\bpy(?:thon3?)?(?:\.exe)?\b", re.IGNORECASE)
# 읽기 전용 조회는 통과시킨다 (cat/grep 등으로 러너를 열어보는 경우).
_READ_ONLY = re.compile(
    r"^\s*(?:cat|head|tail|sed|awk|grep|rg|less|more|wc|nl|type|ls|find|git"
    r"|Get-Content|Select-String|Get-ChildItem)\b",
    re.IGNORECASE,
)


def is_collection_run(tool_name: str, tool_input: dict) -> bool:
    """이 호출이 '새 세션 수집 실행'인가."""
    if tool_name not in SHELL_TOOLS:
        return False
    command = tool_input.get("command")
    if not isinstance(command, str):
        return False
    if not _RUNNER.search(command):
        return False
    if _READ_ONLY.match(command):
        return False
    return bool(_PYTHON.search(command))


def block_message(entry: dict) -> str:
    reason = entry.get("reason", "(사유 미기록)")
    unlock = entry.get("unlock_requires", "(해제 조건 미기록)")
    return (
        "차단됨 — 새 세션 수집 잠금 (harness/gates.json: collection=locked).\n"
        f"이유: {reason}\n"
        f"해제 조건: {unlock}\n"
        "지금 할 일은 데이터를 더 모으는 것이 아니라 채점 방법과 과제 설계를 "
        "정하는 것이다. 잠금을 임의로 풀지 말고 유저에게 확인할 것. "
        "기존 데이터 재분석·재현·버그 수정은 막혀 있지 않다."
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0  # 입력을 못 읽으면 이 훅은 판단하지 않는다.
    if not isinstance(payload, dict):
        return 0

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}

    try:
        if not is_collection_run(str(payload.get("tool_name", "")), tool_input):
            return 0
        # 수집 실행으로 판정된 경우에만 잠금을 본다. 여기서 오류가 나면
        # 통과시키지 않고 막는다 (잠금이 조용히 무력화되면 안 되므로).
        entry = load_gates().get("collection")
        if not isinstance(entry, dict):
            sys.stderr.write(
                "차단됨 — harness/gates.json의 collection 항목을 읽지 못했다. "
                "잠금 상태를 확인할 수 없으므로 수집을 막는다.\n"
            )
            return 2
        if entry.get("state") == "locked":
            sys.stderr.write(block_message(entry) + "\n")
            return 2
        return 0
    except Exception as exc:  # noqa: BLE001 - 잠금은 조용히 실패하면 안 된다
        sys.stderr.write(f"차단됨 — 수집 가드가 오류로 판단 불가: {exc!r}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
