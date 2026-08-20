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

# 파이썬 인터프리터가 러너를 **인자로 받아 실행**하는 형태만 잡는다.
#
# 첫 판은 "run_sessions.py가 들어 있고 어딘가에 py가 있으면" 이었는데, 그
# `\bpy\b`가 `.py` 확장자의 py에 그대로 걸렸다. 그래서 러너를 텍스트로
# 언급하기만 한 명령(이 기능의 PR 본문이 첫 피해자였다)까지 차단됐다.
# 지금은 인터프리터 토큰 바로 뒤에 러너 경로가 오는 경우만 본다.
# 수집을 실행하는 러너들. **새 러너를 만들면 여기에 추가해야 한다** —
# 실제로 `run_chain.py`를 만들었을 때 이 목록이 `run_sessions.py`만 알고 있어
# 새 러너가 잠금을 그냥 통과했다. tests/test_harness.py가 pilot/run_*.py를
# 전수 대조해 그 재발을 막는다.
RUNNERS = ("run_sessions.py", "run_chain.py")

_COLLECTION_RUN = re.compile(
    r"(?:^|[\s;|&(])"  # 명령 시작 위치
    r"(?:[^\s;|&]*[\\/])?"  # .venv/Scripts/ 같은 경로 접두사 (선택).
                            # 경로 구분자로 끝나야 한다 — 아니면
                            # `tests/test_x.py` 의 꼬리 `py` 가 인터프리터로
                            # 읽힌다.
    r"(?:python3?|py)(?:\.exe)?"  # 인터프리터 토큰
    r"(?=\s)"  # 여기서 토큰이 끝나야 한다. 이 둘이 없으면
               # `pytest a.py tests/test_run_chain.py` 가 수집 실행으로
               # 오탐된다 (2026-08-20 실제로 막혔다).
    r"(?:\s+-\S+)*"  # -u, -3 같은 플래그 (선택)
    r"\s+[^\s;|&]*(?:"
    + "|".join(name.replace(".", r"\.") for name in RUNNERS)
    + r")",
    re.IGNORECASE,
)


_QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"", re.DOTALL)


def strip_prose_quotes(command: str) -> str:
    """따옴표 안의 **산문**을 지운다. 그건 실행이 아니라 데이터다.

    커밋 메시지나 PR 본문이 러너 실행 형태를 인용하기만 해도 차단되는 일이
    실제로 있었다(이 가드의 수정 커밋이 두 번째 피해자였다). 반대로 인용된
    **경로**(`python "pilot/run_sessions.py"`)는 진짜 실행이므로 남긴다.
    가르는 기준은 따옴표 안에 공백이 있는가 — 산문에는 있고 경로에는 없다.

    알려진 빈틈: 공백이 든 경로를 따옴표로 감싼 실행은 놓친다. 잠금은
    실수를 막는 장치이지 우회를 막는 장치가 아니므로 감수한다.
    """

    def repl(m: re.Match[str]) -> str:
        inner = m.group(0)[1:-1]
        return " " if re.search(r"\s", inner) else m.group(0)

    return _QUOTED.sub(repl, command)


def is_collection_run(tool_name: str, tool_input: dict) -> bool:
    """이 호출이 '새 세션 수집 실행'인가."""
    if tool_name not in SHELL_TOOLS:
        return False
    command = tool_input.get("command")
    if not isinstance(command, str):
        return False
    return bool(_COLLECTION_RUN.search(strip_prose_quotes(command)))


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
