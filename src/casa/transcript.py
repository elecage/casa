"""Tolerant parser for Claude Code session transcripts (JSONL).

The transcript format is undocumented and version-dependent. This parser
extracts only what the audit needs and NEVER raises on unknown shapes:
unparseable lines and unfamiliar fields are counted and skipped.

Extracted event stream (in file order):
  - ToolCall: every `tool_use` content item in assistant messages
  - tool errors: `tool_result` items with is_error truthy
  - compaction markers: entries with isCompactSummary, or type == "summary"
    appearing after the first message (leading "summary" lines are session
    titles, not compaction)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

READ_TOOLS = {"Read", "Grep", "Glob", "LS", "NotebookRead", "WebFetch", "WebSearch"}
WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
# Tools whose input.command is a shell command line. Claude Code on Windows
# exposes a PowerShell tool alongside Bash; sessions freely mix the two
# (44/60 pilot sessions used PowerShell), so both must be treated as shells
# or shell-level metrics silently undercount.
SHELL_TOOLS = {"Bash", "PowerShell"}

# Shell commands that count as exploration rather than mutation.
# Matched case-insensitively; includes PowerShell cmdlets and their
# common aliases (dir/type/gci/gc/sls map to read-only cmdlets).
_SHELL_EXPLORE_PREFIXES = (
    "ls", "cat", "head", "tail", "grep", "rg", "find", "fd", "tree",
    "git log", "git show", "git diff", "git status", "wc", "file", "stat",
    "get-childitem", "get-content", "get-item", "select-string",
    "test-path", "dir", "type ", "gci", "gc ", "sls",
)

# Leading segments that only change directory before the real command
# (e.g. `cd "x" && pytest`, `Set-Location y; python z`).
_CD_PREFIXES = ("cd ", "cd\t", "set-location ", "pushd ")


def _effective_command(cmd: str) -> str:
    """The first command segment that is not a directory change."""
    for sep in ("&&", ";"):
        parts = [p.strip() for p in cmd.split(sep)]
        if len(parts) > 1 and parts[0].lower().startswith(_CD_PREFIXES):
            return _effective_command(sep.join(parts[1:]).strip())
    return cmd.strip()


@dataclass
class ToolCall:
    index: int                # 0-based order among tool calls
    name: str
    input: dict[str, Any]
    timestamp: str | None
    uuid: str | None
    after_compaction: int     # number of compaction events seen before this call
    is_error: bool = False    # set when a matching tool_result reports an error

    @property
    def shell_command(self) -> str:
        if self.name in SHELL_TOOLS:
            cmd = self.input.get("command", "")
            return cmd if isinstance(cmd, str) else ""
        return ""

    # Backwards-compatible alias (pre-PowerShell name).
    @property
    def bash_command(self) -> str:
        return self.shell_command

    @property
    def is_exploration(self) -> bool:
        if self.name in READ_TOOLS:
            return True
        cmd = _effective_command(self.shell_command)
        return bool(cmd) and cmd.lower().startswith(_SHELL_EXPLORE_PREFIXES)

    @property
    def is_mutation(self) -> bool:
        return self.name in WRITE_TOOLS

    def searchable_text(self) -> str:
        """Text a rule regex is matched against."""
        if self.name in SHELL_TOOLS:
            return self.shell_command
        try:
            return json.dumps(self.input, ensure_ascii=False, sort_keys=True)
        except (TypeError, ValueError):
            return str(self.input)


@dataclass
class Session:
    path: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    n_assistant_messages: int = 0
    n_user_messages: int = 0
    compaction_count: int = 0
    skipped_lines: int = 0
    model_versions: set[str] = field(default_factory=set)
    first_timestamp: str | None = None
    last_timestamp: str | None = None
    # Text of the last assistant message that contained text — the
    # session's final self-report, input to the claim-consistency audit.
    final_assistant_text: str | None = None

    @property
    def n_tool_calls(self) -> int:
        return len(self.tool_calls)


def _iter_content(message: Any) -> Iterator[dict]:
    if not isinstance(message, dict):
        return
    content = message.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                yield item


def parse(path: str | Path) -> Session:
    session = Session(path=str(path))
    pending: dict[str, ToolCall] = {}  # tool_use_id -> ToolCall awaiting result
    saw_message = False

    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                session.skipped_lines += 1
                continue
            if not isinstance(entry, dict):
                session.skipped_lines += 1
                continue

            etype = entry.get("type")
            ts = entry.get("timestamp")
            if isinstance(ts, str):
                session.first_timestamp = session.first_timestamp or ts
                session.last_timestamp = ts

            # --- compaction detection ---------------------------------
            if entry.get("isCompactSummary"):
                session.compaction_count += 1
            elif etype == "summary" and saw_message:
                session.compaction_count += 1

            if etype == "assistant":
                saw_message = True
                session.n_assistant_messages += 1
                msg = entry.get("message")
                if isinstance(msg, dict) and isinstance(msg.get("model"), str):
                    session.model_versions.add(msg["model"])
                texts = [item.get("text") for item in _iter_content(msg)
                         if item.get("type") == "text"
                         and isinstance(item.get("text"), str)]
                if texts:
                    session.final_assistant_text = "\n".join(texts)
                for item in _iter_content(msg):
                    if item.get("type") == "tool_use":
                        call = ToolCall(
                            index=len(session.tool_calls),
                            name=str(item.get("name", "")),
                            input=item.get("input") if isinstance(item.get("input"), dict) else {},
                            timestamp=ts if isinstance(ts, str) else None,
                            uuid=entry.get("uuid"),
                            after_compaction=session.compaction_count,
                        )
                        session.tool_calls.append(call)
                        tuid = item.get("id")
                        if isinstance(tuid, str):
                            pending[tuid] = call

            elif etype == "user":
                saw_message = True
                session.n_user_messages += 1
                for item in _iter_content(entry.get("message")):
                    if item.get("type") == "tool_result":
                        tuid = item.get("tool_use_id")
                        if item.get("is_error") and isinstance(tuid, str) and tuid in pending:
                            pending[tuid].is_error = True

    return session
