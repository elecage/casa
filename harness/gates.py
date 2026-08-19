"""세션 하네스의 공용 유틸 — 잠금 상태 읽기.

표준 라이브러리만 쓴다. 훅은 .venv가 깨져 있어도 최대한 동작해야 하므로
외부 의존성을 두지 않는다.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES = REPO / "harness" / "gates.json"


def load_gates(path: Path | None = None) -> dict:
    """gates.json을 읽는다. 없거나 깨졌으면 빈 dict."""
    p = path or GATES
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def gate_state(name: str, gates: dict | None = None, default: str = "open") -> str:
    g = gates if gates is not None else load_gates()
    entry = g.get(name)
    if not isinstance(entry, dict):
        return default
    state = entry.get("state")
    return state if isinstance(state, str) else default
