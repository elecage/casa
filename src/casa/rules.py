"""Rule specification and matching engine.

Rules are machine-checkable translations of CLAUDE.md-style instructions
(AgentSpec-style trigger/predicate/enforcement; see docs/ARCHITECTURE.md).

Two rule types:
  - prohibit:        tool + regex on the call's searchable text. Violation the
                     moment a matching call occurs. Hook-blockable.
  - require_before:  when `trigger` matches a call, some earlier call must
                     have matched `prerequisite`. Violation at trigger time.

Every rule carries `kind: prohibition|obligation` — the label used by the
H1b differential-decay analysis (see docs/RESEARCH_PLAN.md).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .transcript import Session, ToolCall


@dataclass
class Matcher:
    tool: str          # exact tool name, or "*"
    pattern: str       # regex, searched (not fullmatch)

    def matches(self, call: ToolCall) -> bool:
        if self.tool != "*" and self.tool != call.name:
            return False
        try:
            return re.search(self.pattern, call.searchable_text()) is not None
        except re.error:
            return False


@dataclass
class Rule:
    id: str
    type: str                      # "prohibit" | "require_before"
    kind: str                      # "prohibition" | "obligation"
    severity: str = "medium"
    category: str = "workflow"
    description: str = ""
    action: str = "log"            # "block" | "log" (hook behavior)
    matcher: Matcher | None = None          # for prohibit
    trigger: Matcher | None = None          # for require_before
    prerequisite: Matcher | None = None     # for require_before


@dataclass
class Violation:
    rule_id: str
    kind: str
    severity: str
    call_index: int
    after_compaction: int
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def _matcher(raw: Any) -> Matcher | None:
    if not isinstance(raw, dict):
        return None
    return Matcher(tool=str(raw.get("tool", "*")), pattern=str(raw.get("pattern", "")))


def load_rules(path: str | Path) -> list[Rule]:
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    rules: list[Rule] = []
    for raw in data.get("rules", []):
        if not isinstance(raw, dict) or "id" not in raw:
            continue
        rtype = raw.get("type", "prohibit")
        rule = Rule(
            id=str(raw["id"]),
            type=rtype,
            kind=str(raw.get("kind", "prohibition" if rtype == "prohibit" else "obligation")),
            severity=str(raw.get("severity", "medium")),
            category=str(raw.get("category", "workflow")),
            description=str(raw.get("description", "")),
            action=str(raw.get("action", "log")),
        )
        if rtype == "prohibit":
            rule.matcher = _matcher({"tool": raw.get("tool", "*"), "pattern": raw.get("pattern", "")})
        elif rtype == "require_before":
            rule.trigger = _matcher(raw.get("trigger"))
            rule.prerequisite = _matcher(raw.get("prerequisite"))
        rules.append(rule)
    return rules


def check_call(rules: list[Rule], call: ToolCall) -> list[Rule]:
    """Prohibit-rules matched by a single call (used by the PreToolUse hook)."""
    return [r for r in rules
            if r.type == "prohibit" and r.matcher and r.matcher.matches(call)]


def evaluate(session: Session, rules: list[Rule]) -> list[Violation]:
    """Full-session evaluation (used by the audit engine)."""
    violations: list[Violation] = []
    for rule in rules:
        if rule.type == "prohibit" and rule.matcher:
            for call in session.tool_calls:
                if rule.matcher.matches(call):
                    violations.append(Violation(
                        rule_id=rule.id, kind=rule.kind, severity=rule.severity,
                        call_index=call.index, after_compaction=call.after_compaction,
                        detail=f"prohibited call: {call.name} {call.searchable_text()[:120]}",
                    ))
        elif rule.type == "require_before" and rule.trigger and rule.prerequisite:
            satisfied_at: list[int] = [
                c.index for c in session.tool_calls if rule.prerequisite.matches(c)
            ]
            for call in session.tool_calls:
                if rule.trigger.matches(call):
                    if not any(i < call.index for i in satisfied_at):
                        violations.append(Violation(
                            rule_id=rule.id, kind=rule.kind, severity=rule.severity,
                            call_index=call.index, after_compaction=call.after_compaction,
                            detail=f"trigger without prerequisite: {call.name} "
                                   f"{call.searchable_text()[:120]}",
                        ))
    violations.sort(key=lambda v: v.call_index)
    return violations
