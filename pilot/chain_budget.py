#!/usr/bin/env python3
"""PreToolUse hook: enforce a per-session tool-call budget in chain runs.

A chain splits one project across several sessions, and the split has to be
imposed rather than left to the agent — otherwise where a session stops is
chosen by the thing being measured (docs/MULTISESSION_ARM.md section 5).
The CLI has no turn cap, so the budget is enforced here, in code, which is
also this project's standing rule about enforcement.

Two stages, and the first one matters as much as the second:

    warning    a few calls before the cap, the session is told how many are
               left. Without this window it could never write a handoff note,
               because writing a file is itself a tool call — and the handoff
               is the variable the arm exists to measure.
    block      at the cap, every further tool call is refused. The session can
               still produce a final text message.

"Did it use the warning to leave a handoff?" is therefore an observation, not
a given. That is the discipline dimension, measured rather than assumed.

Configuration comes from the workdir, written by the chain runner:

    .casa-chain.json   {"budget": 60, "warn_at": 55}
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_BUDGET = 60
DEFAULT_WARN_MARGIN = 5
CONFIG_NAME = ".casa-chain.json"


def load_config(start: Path) -> dict:
    """Read the chain config from the working directory, tolerating absence."""
    try:
        raw = json.loads((start / CONFIG_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def count_tool_calls(transcript: Path) -> int:
    """Tool calls issued so far in this session.

    Counted from the transcript rather than kept in a side file: the
    transcript is the record the rest of the project already trusts, and a
    counter file would drift if the session were resumed.
    """
    total = 0
    try:
        text = transcript.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    for line in text.splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict) or entry.get("type") != "assistant":
            continue
        content = (entry.get("message") or {}).get("content")
        if isinstance(content, list):
            total += sum(1 for item in content
                         if isinstance(item, dict) and item.get("type") == "tool_use")
    return total


def decide(used: int, budget: int, warn_at: int) -> tuple[int, str]:
    """(exit code, message). Exit 2 blocks the call; 0 lets it through."""
    if used >= budget:
        return 2, (
            f"세션 예산 소진 — 도구 호출 {used}/{budget}회.\n"
            "더 이상 도구를 쓸 수 없다. 지금까지 한 일과 다음에 이어서 할 일을 "
            "마지막 메시지로 정리하고 끝내라."
        )
    if used >= warn_at:
        return 0, (
            f"세션 예산 경고 — 도구 호출 {used}/{budget}회. "
            f"{budget - used}회 남았다. 남은 호출 안에 작업 상태와 다음에 할 일을 "
            "저장소에 기록으로 남겨라."
        )
    return 0, ""


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    if not isinstance(payload, dict):
        return 0

    workdir = Path(payload.get("cwd") or os.getcwd())
    config = load_config(workdir)
    budget = config.get("budget", DEFAULT_BUDGET)
    if not isinstance(budget, int) or budget <= 0:
        return 0
    warn_at = config.get("warn_at", max(1, budget - DEFAULT_WARN_MARGIN))

    transcript = payload.get("transcript_path")
    if not isinstance(transcript, str):
        return 0
    used = count_tool_calls(Path(transcript))

    code, message = decide(used, budget, warn_at)
    if code == 2:
        sys.stderr.write(message + "\n")
        return 2
    if message:
        json.dump({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "additionalContext": message}},
            sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
