"""Tolerant parser for Claude Code session transcripts (JSONL).

The transcript format is undocumented and version-dependent. This parser
extracts only what the audit needs and NEVER raises on unknown shapes:
unparseable lines and unfamiliar fields are counted and skipped.

Extracted event stream (in file order):
  - ToolCall: every `tool_use` content item in assistant messages
  - tool results: body text, length and hash of the matching `tool_result`
    (see "Result bodies" below), plus the is_error flag
  - compaction markers: entries with isCompactSummary, or type == "summary"
    appearing after the first message (leading "summary" lines are session
    titles, not compaction)

Result bodies
-------------
Progress judgement (docs/PROGRESS_RULE.md) asks whether a call produced
anything new, which cannot be answered from the call's *input* alone: two
identical `pytest` invocations differ only in what they printed. So the
result body is kept.

Bodies are unbounded in principle (a `cat` of a large file), so `result_text`
is capped at `max_result_chars` and `result_truncated` records that it was
cut. `result_hash` is taken over the *full* body before truncation, so exact
identity comparisons stay correct even for outputs past the cap.

Observed shapes (2026-08-19, one 634-line session): 129 results carried a
plain string body, 2 carried a list of content blocks. Both are handled;
anything else yields None rather than raising.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

# Cap on the retained result body per call. Generous enough that ordinary
# command output survives whole, small enough that loading ~130 sessions for
# batch analysis does not blow up memory.
MAX_RESULT_CHARS = 200_000

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
    # --- result of the call, filled in when a matching tool_result arrives ---
    result_text: str | None = None    # body, truncated to MAX_RESULT_CHARS
    result_len: int = 0               # length of the *full* body, in characters
    result_hash: str | None = None    # sha256 of the full body, before truncation
    result_truncated: bool = False

    @property
    def has_result(self) -> bool:
        """False when no tool_result was matched (e.g. a session cut mid-call)."""
        return self.result_hash is not None

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


def _result_body(item: dict) -> str | None:
    """Body text of a tool_result, across the shapes the format uses.

    A plain string is the common case. A list of content blocks appears for
    mixed results (text plus images); the text blocks are joined and the rest
    ignored. Unknown shapes give None — never an exception.
    """
    content = item.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            block["text"]
            for block in content
            if isinstance(block, dict) and isinstance(block.get("text"), str)
        ]
        return "\n".join(parts) if parts else None
    return None


def _attach_result(call: ToolCall, body: str, max_result_chars: int) -> None:
    call.result_len = len(body)
    call.result_hash = hashlib.sha256(body.encode("utf-8", "replace")).hexdigest()
    if max_result_chars >= 0 and len(body) > max_result_chars:
        call.result_text = body[:max_result_chars]
        call.result_truncated = True
    else:
        call.result_text = body


def parse(path: str | Path, max_result_chars: int = MAX_RESULT_CHARS) -> Session:
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
                    if item.get("type") != "tool_result":
                        continue
                    tuid = item.get("tool_use_id")
                    if not isinstance(tuid, str) or tuid not in pending:
                        continue
                    call = pending[tuid]
                    if item.get("is_error"):
                        call.is_error = True
                    body = _result_body(item)
                    if body is not None:
                        _attach_result(call, body, max_result_chars)

    return session
