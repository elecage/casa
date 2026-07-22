#!/usr/bin/env python3
"""Stop hook: score the finished session and drop a report in .casa/reports/.

Claude Code sends {"transcript_path": ..., "stop_hook_active": ...} on stdin.
Always exits 0 — the auditor must never block session termination.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "src"))

from casa.audit import audit_session, to_markdown  # noqa: E402
from casa.rules import load_rules  # noqa: E402


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        transcript = payload.get("transcript_path")
        if not transcript or not Path(transcript).exists():
            return 0

        rules = None
        rules_env = os.environ.get("CASA_RULES")
        proj = os.environ.get("CLAUDE_PROJECT_DIR", ".")
        candidates = [rules_env, str(Path(proj) / "rules" / "rules.yaml")]
        for cand in candidates:
            if cand and Path(cand).exists():
                rules = load_rules(cand)
                break

        result = audit_session(transcript, rules=rules)
        out_dir = Path(proj) / ".casa" / "reports"
        out_dir.mkdir(parents=True, exist_ok=True)
        name = Path(transcript).stem + ".md"
        (out_dir / name).write_text(to_markdown(result), encoding="utf-8")
        (out_dir / (Path(transcript).stem + ".json")).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass  # never break the session
    return 0


if __name__ == "__main__":
    sys.exit(main())
