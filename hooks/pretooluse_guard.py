#!/usr/bin/env python3
"""PreToolUse hook: enforce (or log) prohibit-rules before a tool call runs.

Wire-up: see hooks/settings.example.json. Claude Code sends the pending call
as JSON on stdin: {"tool_name": ..., "tool_input": ..., "transcript_path": ...}.

Behavior per matched rule:
  action: block -> exit(2) with reason on stderr (Claude sees it and must adapt)
  action: log   -> record to .casa/events.jsonl, allow the call (pilot mode)

Env:
  CASA_RULES  path to rules yaml (default: <repo>/rules/rules.yaml relative to
              CLAUDE_PROJECT_DIR, falling back to this file's repo)
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "src"))

from casa.rules import check_call, load_rules  # noqa: E402
from casa.transcript import ToolCall  # noqa: E402


def _rules_path() -> Path:
    if os.environ.get("CASA_RULES"):
        return Path(os.environ["CASA_RULES"])
    proj = os.environ.get("CLAUDE_PROJECT_DIR")
    if proj and (Path(proj) / "rules" / "rules.yaml").exists():
        return Path(proj) / "rules" / "rules.yaml"
    return _REPO / "rules" / "rules.example.yaml"


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # malformed input: never break the session

    call = ToolCall(
        index=-1,
        name=str(payload.get("tool_name", "")),
        input=payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {},
        timestamp=None,
        uuid=None,
        after_compaction=0,
    )

    rules_file = _rules_path()
    if not rules_file.exists():
        return 0
    try:
        matched = check_call(load_rules(rules_file), call)
    except Exception:
        return 0  # a broken rules file must not take the session down

    if not matched:
        return 0

    # Log every match (block or not) for the study.
    log_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")) / ".casa"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        with open(log_dir / "events.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "ts": datetime.now(timezone.utc).isoformat(),
                "tool": call.name,
                "text": call.searchable_text()[:300],
                "rules": [r.id for r in matched],
                "blocked": any(r.action == "block" for r in matched),
            }, ensure_ascii=False) + "\n")
    except OSError:
        pass

    blockers = [r for r in matched if r.action == "block"]
    if blockers:
        reasons = "; ".join(f"{r.id}: {r.description or 'rule violation'}" for r in blockers)
        print(f"BLOCKED by CASA rule(s) — {reasons}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
