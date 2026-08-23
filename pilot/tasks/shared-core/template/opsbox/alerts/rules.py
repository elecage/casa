"""Reads the rules file. The format is in `docs/alerts.md`.

One rule puts one threshold on one account. `basis` says what that threshold
is compared against.
"""

from __future__ import annotations

import json
from pathlib import Path

#: Where the rules file lives.
RULES_FILE = "alert-rules.json"


def load(root: Path) -> list[dict]:
    path = Path(root) / RULES_FILE
    if not path.is_file():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw.get("rules", []) if isinstance(raw, dict) else list(raw)
