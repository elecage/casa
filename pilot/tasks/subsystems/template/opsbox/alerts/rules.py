"""규칙 파일을 읽는다. 형식은 `docs/alerts.md`.

규칙 하나는 계정 하나에 문턱 하나를 건다. `basis`가 그 문턱을 무엇에
견주는지 말한다.
"""

from __future__ import annotations

import json
from pathlib import Path

#: 규칙 파일이 놓이는 자리.
RULES_FILE = "alert-rules.json"


def load(root: Path) -> list[dict]:
    path = Path(root) / RULES_FILE
    if not path.is_file():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw.get("rules", []) if isinstance(raw, dict) else list(raw)
