#!/usr/bin/env python3
"""SessionStart 훅: 목표·미해결 문제·잠금 상태를 매 세션에 강제 주입한다.

이 프로젝트의 규칙은 문서에 다 적혀 있었는데도 지켜지지 않은 이력이 있다
(수집 배치 7세션이 3주 넘게 STATUS.md에 없었다). 문서를 읽기를 기대하는
대신, 세션이 시작될 때 무조건 컨텍스트에 들어가게 한다.

계약: SessionStart 훅의 **plain stdout이 컨텍스트로 들어간다**. exit 0.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gates import REPO, load_gates  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")


def render(gates: dict, anchor: str) -> str:
    lines = [anchor.rstrip(), "", "## 현재 잠금 상태 (harness/gates.json)", ""]
    if not gates:
        lines.append("- 잠금 파일을 읽지 못했다. `harness/gates.json`을 확인할 것.")
        return "\n".join(lines) + "\n"
    for name, entry in gates.items():
        if name.startswith("_") or not isinstance(entry, dict):
            continue
        state = entry.get("state", "?")
        mark = "잠김" if state == "locked" else state
        lines.append(f"- **{name} = {mark}**")
        if entry.get("blocks"):
            lines.append(f"  - 막는 것: {entry['blocks']}")
        if state == "locked":
            if entry.get("reason"):
                lines.append(f"  - 이유: {entry['reason']}")
            if entry.get("unlock_requires"):
                lines.append(f"  - 해제 조건: {entry['unlock_requires']}")
    return "\n".join(lines) + "\n"


def main() -> int:
    try:
        anchor = (REPO / "harness" / "anchor.md").read_text(encoding="utf-8")
    except OSError:
        anchor = "# 경고\n\n`harness/anchor.md`를 읽지 못했다. 하네스가 깨져 있다.\n"
    sys.stdout.write(render(load_gates(), anchor))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
