"""Progress judgement — did this call produce anything new?

Design and rationale: `docs/PROGRESS_RULE.md`. Short version: progress is not
one thing. Reading changes nothing on disk yet is progress; editing the wrong
file changes disk yet is not. So each call gets three verdicts.

    knowledge  did the session learn something it did not know?   0 / +1
    artifact   did the project actually change?                  -1 / 0 / +1
    evidence   did a check come back different than before?       0 / +1

Why three and not one: the largest waste category in failing coding-agent
trajectories is "repairing the wrong problem" (24% of failures, 39% of wasted
steps). There the session keeps editing and the outputs keep differing, so
every single-axis definition of progress reports success. Split apart, it has
a distinctive shape: artifact keeps rising while evidence stays flat.

The tracker is incremental by construction — `observe()` takes one call at a
time and never looks ahead. That is what the external app needs: it tails an
append-only transcript and cannot see the future (`docs/ARCHITECTURE.md`).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

from .metrics import _is_aux_check, _is_test_run
from .transcript import SHELL_TOOLS, WRITE_TOOLS, ToolCall, _effective_command

# --------------------------------------------------------------- normalize

# Only *known-volatile* patterns are erased. Digits in general are never
# touched: blurring them would turn "3 failed, 5 passed" into "N failed,
# N passed" and kill the evidence axis outright.
_VOLATILE = [
    re.compile(r"\x1b\[[0-9;]*[A-Za-z]"),                      # ANSI colour
    re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}"
               r"(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?"),           # ISO timestamp
    re.compile(r"\b\d{1,2}:\d{2}:\d{2}\b"),                     # clock / elapsed
    re.compile(r"\b\d+(?:\.\d+)?\s?(?:ms|s|sec|secs|seconds)\b"),  # durations
    re.compile(r"\b0x[0-9a-fA-F]+\b"),                          # addresses
    re.compile(r"[A-Za-z]:[\\/](?:Users|Windows)[\\/][^\s\"']*[Tt]emp[^\s\"']*"),
    re.compile(r"/tmp/[^\s\"']*"),
]
_PLACEHOLDER = "\x00"


def normalize(text: str) -> str:
    """Erase known-volatile substrings so the same work hashes the same way.

    Two runs of one test differ in elapsed time and nothing else; without this
    they would read as "the evidence changed".
    """
    out = text.replace("\r\n", "\n").replace("\\", "/")
    for pattern in _VOLATILE:
        out = pattern.sub(_PLACEHOLDER, out)
    return "\n".join(line.rstrip() for line in out.split("\n")).strip()


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def normalized_hash(text: str | None) -> str | None:
    return None if text is None else _digest(normalize(text))


# ----------------------------------------------------------- call taxonomy

# Shell commands that write. Explicit, like transcript._SHELL_EXPLORE_PREFIXES:
# guessing from the verb is how the earlier shell blind spot happened.
_SHELL_MUTATE_PREFIXES = (
    "rm", "rmdir", "mv", "cp", "mkdir", "touch", "ln", "chmod", "chown",
    "tee", "patch", "dd", "truncate", "make", "install",
    "git add", "git commit", "git checkout", "git apply", "git rm", "git mv",
    "git reset", "git stash", "git merge", "git rebase", "git push",
    "git pull", "git clean", "git restore",
    "npm install", "npm ci", "pip install", "poetry install", "uv pip",
    "remove-item", "new-item", "move-item", "copy-item", "rename-item",
    "set-content", "add-content", "out-file", "set-itemproperty",
)
# `sed -i` edits in place; plain `sed` does not.
_SED_INPLACE = re.compile(r"\bsed\b[^|;]*\s-i\b")
# Redirection into a file. `2>&1` merges streams and is not a write.
# 널 장치로 보내는 것은 파일을 쓰는 것이 아니다. `2>/dev/null` 을 파일
# 쓰기로 세면 조사만 한 호출이 산출물 진전으로 잡힌다 (2026-08-20 프로브에서
# 드러났다 — `ls ... 2>/dev/null` 세 건이 파일을 바꾼 호출로 세어졌다).
_REDIRECT = re.compile(r">>?\s*(?![&\s])(?!/dev/null\b)(?!nul\b)",
                       re.IGNORECASE)
_QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"", re.DOTALL)


def _outside_quotes(command: str) -> str:
    """The command with quoted spans blanked out.

    A `>` inside quotes is not a redirection. Measured on real sessions before
    this was added: 87 of 90 shell calls flagged as writes were actually
    `python -c "...x > 0..."` analysis snippets and quoted commit messages.
    Those are verification calls, so miscounting them moved work off the
    evidence axis and onto the artifact axis — inverting the one shape the
    three-way rule exists to detect.
    """
    return _QUOTED.sub(" ", command)


def is_mutating_shell(call: ToolCall) -> bool:
    if call.name not in SHELL_TOOLS:
        return False
    cmd = _effective_command(call.shell_command)
    if not cmd:
        return False
    low = cmd.lower()
    if low.startswith(_SHELL_MUTATE_PREFIXES):
        return True
    bare = _outside_quotes(cmd)
    return bool(_SED_INPLACE.search(bare.lower()) or _REDIRECT.search(bare))


def is_verification(call: ToolCall) -> bool:
    return _is_test_run(call) or _is_aux_check(call)


def _query_key(call: ToolCall) -> str:
    """Identity of a look-up: same key means 'the session asked this before'."""
    if call.name in SHELL_TOOLS:
        return f"{call.name}:{normalize(call.shell_command)}"
    try:
        payload = json.dumps(call.input, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        payload = str(call.input)
    return f"{call.name}:{payload}"


def _edit_pairs(call: ToolCall) -> list[tuple[str, str]]:
    """(old, new) text pairs an edit applies, across Edit/MultiEdit shapes."""
    inp = call.input
    edits = inp.get("edits")
    if isinstance(edits, list):
        return [
            (str(e.get("old_string", "")), str(e.get("new_string", "")))
            for e in edits
            if isinstance(e, dict)
        ]
    if "old_string" in inp or "new_string" in inp:
        return [(str(inp.get("old_string", "")), str(inp.get("new_string", "")))]
    if "content" in inp:  # Write: full replacement, no prior text
        return [("", str(inp.get("content", "")))]
    return []


def _path_of(call: ToolCall) -> str:
    for key in ("file_path", "path", "notebook_path"):
        value = call.input.get(key)
        if isinstance(value, str):
            return value.replace("\\", "/")
    return ""


# ---------------------------------------------------------------- verdicts


@dataclass
class ProgressVerdict:
    index: int
    knowledge: int = 0
    artifact: int = 0
    evidence: int = 0
    reason: str = ""          # short label, usable in an alert line

    @property
    def is_progress(self) -> bool:
        return self.knowledge > 0 or self.artifact > 0 or self.evidence > 0

    @property
    def is_standstill(self) -> bool:
        """Nothing learned, nothing changed, nothing newly confirmed."""
        return self.knowledge == 0 and self.artifact == 0 and self.evidence == 0


@dataclass
class ProgressTracker:
    """Streaming progress judgement. Feed calls in order; never looks ahead."""

    # knowledge memory — reset on compaction (the session legitimately forgot)
    _seen_lookups: dict[str, str | None] = field(default_factory=dict)
    _seen_errors: set[str] = field(default_factory=set)
    # artifact memory — never reset; the files are real whether or not the
    # session remembers them
    _edit_history: dict[str, list[tuple[str, str]]] = field(default_factory=dict)
    _write_states: dict[str, list[str]] = field(default_factory=dict)
    _untrusted_paths: set[str] = field(default_factory=set)
    # evidence memory — never reset, keyed on the result not the command
    _seen_checks: set[str] = field(default_factory=set)
    # bookkeeping
    _compactions: int = 0
    structured_mutations: int = 0
    shell_mutations: int = 0

    @property
    def state_confidence(self) -> float:
        """Share of file changes we could actually track.

        Shell writes (`sed -i`, redirection) do not say what they changed, so
        revert detection degrades. Reporting the share beats pretending.
        """
        total = self.structured_mutations + self.shell_mutations
        return 1.0 if total == 0 else self.structured_mutations / total

    def observe(self, call: ToolCall) -> ProgressVerdict:
        if call.after_compaction > self._compactions:
            self._compactions = call.after_compaction
            self._seen_lookups.clear()
            self._seen_errors.clear()

        verdict = ProgressVerdict(index=call.index)
        repeat_error = self._score_errors(call, verdict)

        if call.name in WRITE_TOOLS:
            self._score_structured_edit(call, verdict)
        elif is_mutating_shell(call):
            self._score_shell_mutation(call, verdict)
        elif is_verification(call):
            self._score_verification(call, verdict)
        else:
            self._score_lookup(call, verdict, suppress=repeat_error)
        return verdict

    # -- axes ------------------------------------------------------------

    def _score_errors(self, call: ToolCall, verdict: ProgressVerdict) -> bool:
        """A first-time error is information. The same error again is not.

        Returns True when this is an error we have already seen, so the lookup
        scorer below does not hand out knowledge for it. Without that, varying
        the command slightly and collecting the same failure would read as
        learning — which is the shape of thrashing, not of learning.
        """
        if not call.is_error or not call.result_text:
            return False
        signature = _digest(normalize(call.result_text)[:400])
        if signature in self._seen_errors:
            verdict.reason = "repeat-error"
            return True
        self._seen_errors.add(signature)
        verdict.knowledge = 1
        verdict.reason = "new-error"
        return False

    def _score_lookup(self, call: ToolCall, verdict: ProgressVerdict,
                      suppress: bool = False) -> None:
        key = _query_key(call)
        digest = normalized_hash(call.result_text)
        first_time = key not in self._seen_lookups
        changed = (not first_time and digest is not None
                   and digest != self._seen_lookups[key])
        # Memory is updated either way: the question has now been asked.
        self._seen_lookups[key] = digest
        if suppress:
            return
        if first_time:
            verdict.knowledge = 1
            verdict.reason = verdict.reason or "new-lookup"
        elif changed:
            # Same question, different answer — the world moved.
            verdict.knowledge = 1
            verdict.reason = verdict.reason or "changed-lookup"
        else:
            verdict.reason = verdict.reason or "repeat-lookup"

    def _score_structured_edit(self, call: ToolCall, verdict: ProgressVerdict) -> None:
        self.structured_mutations += 1
        path = _path_of(call)
        if "content" in call.input and call.name != "NotebookEdit":
            self._score_full_write(call, verdict, path)
            return

        pairs = [(o, n) for o, n in _edit_pairs(call) if o != n]
        if not pairs:
            verdict.reason = "no-op-edit"
            return

        history = self._edit_history.setdefault(path, [])
        trusted = path not in self._untrusted_paths
        outcome = 0
        for old, new in pairs:
            if trusted and (new, old) in history:
                outcome = min(outcome, -1)      # undoes an earlier edit
            elif (old, new) in history:
                outcome = max(outcome, 0)       # same edit again: no new state
            else:
                outcome = 1
                break
        history.extend(pairs)

        verdict.artifact = outcome
        verdict.reason = {1: "new-content", 0: "repeat-edit", -1: "revert"}[outcome]

    def _score_full_write(self, call: ToolCall, verdict: ProgressVerdict,
                          path: str) -> None:
        """Write replaces the whole file, so the state is directly knowable.

        The edit-pair heuristic used for Edit cannot see reverts here: every
        Write looks like ("", content) and no inverse pair ever appears. With
        full content in hand the documented rule applies literally — a hash we
        have held before is a revert, not a change.
        """
        digest = _digest(str(call.input.get("content", "")))
        seen = self._write_states.setdefault(path, [])
        if seen and seen[-1] == digest:
            verdict.reason = "no-op-edit"
            return
        if digest in seen and path not in self._untrusted_paths:
            verdict.artifact = -1
            verdict.reason = "revert"
        else:
            verdict.artifact = 1
            verdict.reason = "new-content"
        seen.append(digest)

    def _score_shell_mutation(self, call: ToolCall, verdict: ProgressVerdict) -> None:
        self.shell_mutations += 1
        command = call.shell_command
        for path in self._edit_history:
            tail = path.rsplit("/", 1)[-1]
            if tail and tail in command:
                self._untrusted_paths.add(path)
        verdict.artifact = 0 if call.is_error else 1
        verdict.reason = verdict.reason or ("failed-shell-write" if call.is_error
                                            else "shell-write")

    def _score_verification(self, call: ToolCall, verdict: ProgressVerdict) -> None:
        """Evidence is keyed on the *result*, not on the command.

        Keying on the command let a session vary its check slightly — a
        different `-k` selector each time — and collect the same answer over
        and over while every run scored as fresh evidence. That is the same
        hole already closed on the error axis: the information is what came
        back, not what was typed.
        """
        digest = normalized_hash(call.result_text)
        if digest is None:
            verdict.reason = verdict.reason or "check-no-result"
            return
        if digest not in self._seen_checks:
            self._seen_checks.add(digest)
            verdict.evidence = 1
            verdict.reason = verdict.reason or "new-check-result"
        else:
            verdict.reason = verdict.reason or "same-check"


# ------------------------------------------------------------- session API


def progress_series(session) -> list[ProgressVerdict]:
    tracker = ProgressTracker()
    return [tracker.observe(call) for call in session.tool_calls]


def progress_summary(session) -> dict[str, Any]:
    """Per-session roll-up. The alarm rules read the series, not this."""
    tracker = ProgressTracker()
    verdicts = [tracker.observe(call) for call in session.tool_calls]

    longest = run = 0
    for verdict in verdicts:
        run = run + 1 if verdict.is_standstill else 0
        longest = max(longest, run)

    return {
        "n_calls": len(verdicts),
        "knowledge_gains": sum(1 for v in verdicts if v.knowledge > 0),
        "artifact_gains": sum(1 for v in verdicts if v.artifact > 0),
        "reverts": sum(1 for v in verdicts if v.artifact < 0),
        "evidence_gains": sum(1 for v in verdicts if v.evidence > 0),
        "standstill_calls": sum(1 for v in verdicts if v.is_standstill),
        "longest_standstill_run": longest,
        "progress_density": (
            sum(1 for v in verdicts if v.is_progress) / len(verdicts)
            if verdicts else 0.0
        ),
        "state_confidence": tracker.state_confidence,
        "shell_mutations": tracker.shell_mutations,
    }
