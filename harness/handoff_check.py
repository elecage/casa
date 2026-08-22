#!/usr/bin/env python3
"""Stop 훅: 파일을 고쳤는데 인계를 안 남기고 끝내려 하면 한 번 되돌려보낸다.

**왜 필요한가.** `CLAUDE.md`의 "Session handoff" 절이 "작업 상태가 바뀌면
같은 커밋에서 `STATUS.md`를 갱신한다"고 적어 두었는데, 그 규칙만으로는
지켜지지 않았다 — 수집 배치 일곱 세션 분량이 3주 동안 기록되지 않은 채
남아 있었고, 그 일 때문에 `harness/`가 생겼다.

pre-commit 훅은 **커밋마다** `STATUS.md`가 같이 들어갔는지 본다. 이 훅이
보는 것은 다른 것이다 — **세션이 끝나는 시점에** 다음 세션이 이어받을 것이
적혀 있는가. 커밋을 안 하고 끝내는 세션은 pre-commit 훅에 걸리지 않는다.

**문서에 규약을 적는 것과 종료 직전에 말해 주는 것은 다르다**(2026-08-21
유저 지시). 이 훅이 종료 직전에 말해 주는 쪽이다.

**세션당 한 번만** 차단한다. 계약: stdin JSON의 `transcript_path`가 이
세션의 기록이고, exit 2면 종료를 막고 stderr가 모델에 전달된다.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gates import REPO  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

#: 이 저장소의 인계 문서.
HANDOFF = "STATUS.md"

#: 파일을 바꾸는 도구들.
WRITE_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}

#: 이것만 고치고 끝난 세션은 인계를 요구하지 않는다. 인계 문서 자체와
#: 임시 파일이다.
EXEMPT = ("STATUS.md", "/tmp/", "\\tmp\\", ".casa/")


def _paths(call: dict) -> list[str]:
    """그 호출이 건드린 경로들. 셸 명령도 본다."""
    out = []
    payload = call.get("input") or {}
    for key in ("file_path", "path", "notebook_path"):
        value = payload.get(key)
        if isinstance(value, str):
            out.append(value.replace("\\", "/"))
    command = payload.get("command")
    if isinstance(command, str):
        out.append(command.replace("\\", "/"))
    return out


def read_calls(transcript: Path) -> list[dict]:
    """기록에서 도구 호출만 뽑는다. 파서는 관용적이어야 한다 —
    모르는 줄에서 죽으면 훅이 세션을 막는다."""
    calls = []
    try:
        lines = transcript.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return calls
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        message = row.get("message") if isinstance(row, dict) else None
        content = (message or {}).get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            continue
        for item in content:
            if isinstance(item, dict) and item.get("type") == "tool_use":
                calls.append({"name": item.get("name"),
                              "input": item.get("input")})
    return calls


def changed_files(calls: list[dict]) -> bool:
    """인계를 요구할 만큼 무엇인가를 고쳤는가."""
    for call in calls:
        if call.get("name") not in WRITE_TOOLS:
            continue
        for path in _paths(call):
            if not any(spot in path for spot in EXEMPT):
                return True
    return False


def wrote_handoff(calls: list[dict]) -> bool:
    """이 세션이 인계 문서를 고쳤는가."""
    return any(call.get("name") in WRITE_TOOLS
               and any(HANDOFF in path for path in _paths(call))
               for call in calls)


def build_message() -> str:
    return (
        "인계 검사 — 파일을 고쳤는데 `STATUS.md`를 손대지 않고 끝내려 한다.\n"
        "다음 세션은 이 저장소와 `STATUS.md`만 보고 시작한다. 지금 적어 두지\n"
        "않으면 그 세션은 무엇이 끝났고 무엇이 남았는지 알 길이 없다.\n"
        "끝내기 전에 `STATUS.md`에 셋을 적을 것: (1) 이번 세션이 한 일,\n"
        "(2) 남은 일, (3) '다음 세션 시작점'을 지금 상태에 맞게 고칠 것.\n"
        "결정을 내렸으면 결정 로그에도 날짜와 함께 남긴다.\n"
        "이 검사는 세션당 한 번만 뜬다."
    )


def _marker(session_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", session_id or "unknown")[:80]
    return REPO / ".casa" / "harness" / f"handoff_check_{safe}.marker"


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    if not isinstance(payload, dict):
        return 0
    if payload.get("stop_hook_active"):
        return 0

    transcript = payload.get("transcript_path")
    if not isinstance(transcript, str) or not transcript:
        return 0
    calls = read_calls(Path(transcript))
    if not calls:
        return 0
    if not changed_files(calls) or wrote_handoff(calls):
        return 0

    marker = _marker(str(payload.get("session_id", "")))
    if marker.exists():
        return 0
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("blocked once\n", encoding="utf-8")
    except OSError:
        pass                               # 마커를 못 써도 차단은 한다

    sys.stderr.write(build_message() + "\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
