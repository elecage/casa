"""Behavioral metrics computed from a parsed Session.

All metrics are black-box: derived from the local transcript only, with no
ground-truth labels and no model internals. See docs/PILOT_DESIGN.md for how
they are used in the study.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

from .transcript import SHELL_TOOLS, Session, ToolCall


def _normalized_key(call: ToolCall) -> tuple[str, str]:
    return (call.name, " ".join(call.searchable_text().split()))


def exploration_before_first_edit(session: Session) -> int:
    """Number of exploration calls before the first mutating call.

    Returns the total exploration count if the session never mutates.
    """
    n = 0
    for call in session.tool_calls:
        if call.is_mutation:
            return n
        if call.is_exploration:
            n += 1
    return n


def files_read(session: Session) -> set[str]:
    out: set[str] = set()
    for call in session.tool_calls:
        if call.name == "Read":
            fp = call.input.get("file_path")
            if isinstance(fp, str):
                out.add(fp)
    return out


def coverage(session: Session, relevant_files: list[str] | None) -> float | None:
    """Fraction of pre-defined relevant files the session actually read.

    `relevant_files` comes from the per-task config in the pilot; None means
    coverage is not applicable for this session.
    """
    if not relevant_files:
        return None
    seen = {str(Path(p)) for p in files_read(session)}
    hit = sum(1 for f in relevant_files if str(Path(f)) in seen
              or any(s.endswith(str(Path(f))) for s in seen))
    return hit / len(relevant_files)


def max_repetition(session: Session) -> int:
    """Highest number of times an identical (tool, normalized input) call
    was issued. 1 = no repetition; >=3 is a loop smell."""
    counts = Counter(_normalized_key(c) for c in session.tool_calls)
    return max(counts.values(), default=0)


def consecutive_repetition(session: Session) -> int:
    """Longest run of back-to-back identical calls."""
    best, run = 0, 0
    prev = None
    for call in session.tool_calls:
        key = _normalized_key(call)
        run = run + 1 if key == prev else 1
        best = max(best, run)
        prev = key
    return best


def tool_error_rate(session: Session) -> float:
    if not session.tool_calls:
        return 0.0
    return sum(1 for c in session.tool_calls if c.is_error) / len(session.tool_calls)


# --- verification behavior (claim-consistency audit inputs) ------------
# Pilot finding (docs/PILOT_RESULTS.md sections 9-10): whether a session
# actually ran verification before asserting completion separated success
# from failure on the hidden-oracle task, while the assertion itself was
# uniformly confident and carried no signal.


def _is_test_run(call: ToolCall) -> bool:
    return call.name in SHELL_TOOLS and "pytest" in call.shell_command


def _is_aux_check(call: ToolCall) -> bool:
    return (call.name in SHELL_TOOLS and "python" in call.shell_command
            and "pytest" not in call.shell_command)


def verification_signals(session: Session) -> dict[str, int]:
    """Content-based verification behavior: test runs, edit->test cycles,
    ad-hoc python self-checks, and whether the last edit was followed by
    a test run before the session ended."""
    calls = session.tool_calls
    edits = [c.index for c in calls if c.is_mutation]
    first_edit = edits[0] if edits else None
    last_edit = edits[-1] if edits else None
    tests = [c.index for c in calls if _is_test_run(c)]
    checks = [c.index for c in calls if _is_aux_check(c)]
    cycles = 0
    for j, e in enumerate(edits):
        nxt = edits[j + 1] if j + 1 < len(edits) else float("inf")
        if any(e < t < nxt for t in tests):
            cycles += 1
    return {
        "n_test_runs": len(tests),
        "tests_after_first_edit":
            sum(1 for t in tests if first_edit is not None and t > first_edit),
        "edit_test_cycles": cycles,
        "aux_python_checks": len(checks),
        "verified_end": int(bool(tests and last_edit is not None
                                 and max(tests) > last_edit)),
    }


# Explicit completion assertions only; infinitives like "to complete"
# do not count (a stalled pilot session ended on exactly that phrase).
_CLAIM_RE = re.compile(
    r"all \d+ tests pass|tests pass|\bdone\b|\bcompleted\b"
    r"|commit is (done|in|made)", re.IGNORECASE)


def claims_completion(final_text: str | None) -> bool:
    """True when a final self-report asserts completion/success."""
    return bool(final_text) and _CLAIM_RE.search(final_text) is not None


# --- trajectory-level metrics (RQ2 AUROC@k inputs, RQ3 divergence) -----


def step_series(session: Session,
                relevant_files: list[str] | None = None) -> list[dict[str, Any]]:
    """One row per tool call with signals cumulative up to that call —
    the per-step inputs for time-resolved prediction (AUROC@k).

    The final row's cumulative values agree with the whole-session
    metrics in compute_all() (pinned by tests).
    """
    relevant_norm = [str(Path(f)) for f in (relevant_files or [])]
    seen_files: set[str] = set()
    rows: list[dict[str, Any]] = []
    cum_explore = cum_errors = 0
    first_mutation_at: int | None = None

    for call in session.tool_calls:
        if call.is_exploration:
            cum_explore += 1
        if call.is_error:
            cum_errors += 1
        if call.is_mutation and first_mutation_at is None:
            first_mutation_at = call.index
        if call.name == "Read":
            fp = call.input.get("file_path")
            if isinstance(fp, str):
                seen_files.add(str(Path(fp)))

        coverage_k = None
        if relevant_norm:
            hit = sum(1 for f in relevant_norm
                      if f in seen_files or any(s.endswith(f) for s in seen_files))
            coverage_k = round(hit / len(relevant_norm), 4)

        rows.append({
            "index": call.index,
            "tool": call.name,
            "after_compaction": call.after_compaction,
            "cum_exploration": cum_explore,
            "cum_files_read": len(seen_files),
            "cum_coverage": coverage_k,
            "cum_errors": cum_errors,
            "cum_error_rate": round(cum_errors / (call.index + 1), 4),
            "mutated": first_mutation_at is not None,
        })
    return rows


def tool_sequence(session: Session) -> list[str]:
    """Coarse action sequence for cross-session comparison. Shell calls
    (Bash or PowerShell) carry their leading word as "Shell:git" so the
    shell choice itself does not split otherwise-identical trajectories;
    other tools contribute their name."""
    seq = []
    for call in session.tool_calls:
        if call.name in SHELL_TOOLS:
            head = call.shell_command.strip().split()
            seq.append(f"Shell:{head[0].lower()}" if head else "Shell")
        else:
            seq.append(call.name)
    return seq


def normalized_edit_distance(seq_a: list[str], seq_b: list[str]) -> float:
    """Levenshtein distance over action sequences, normalized to [0, 1]
    by the longer length. 0.0 = identical trajectories."""
    if not seq_a and not seq_b:
        return 0.0
    prev = list(range(len(seq_b) + 1))
    for i, a in enumerate(seq_a, 1):
        cur = [i]
        for j, b in enumerate(seq_b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1,
                           prev[j - 1] + (a != b)))
        prev = cur
    return round(prev[-1] / max(len(seq_a), len(seq_b)), 4)


def prefix_divergence(seq_a: list[str], seq_b: list[str]) -> int:
    """Index of the first differing action — how many steps two sessions
    stayed on the same path (RQ3: when do trajectories split?)."""
    k = 0
    for a, b in zip(seq_a, seq_b):
        if a != b:
            break
        k += 1
    return k


def compute_all(session: Session, relevant_files: list[str] | None = None) -> dict[str, Any]:
    tool_counts = Counter(c.name for c in session.tool_calls)
    return {
        "n_tool_calls": session.n_tool_calls,
        "n_assistant_messages": session.n_assistant_messages,
        "n_user_messages": session.n_user_messages,
        "tool_counts": dict(tool_counts),
        "exploration_before_first_edit": exploration_before_first_edit(session),
        "files_read_count": len(files_read(session)),
        "coverage": coverage(session, relevant_files),
        "max_repetition": max_repetition(session),
        "consecutive_repetition": consecutive_repetition(session),
        "tool_error_rate": round(tool_error_rate(session), 4),
        "compaction_count": session.compaction_count,
        "skipped_lines": session.skipped_lines,
        "model_versions": sorted(session.model_versions),
        **verification_signals(session),
        "claims_completion": claims_completion(session.final_assistant_text),
        # completion asserted with no test run after the last edit —
        # the deterministic "said done without checking" flag
        "unverified_completion_claim": bool(
            claims_completion(session.final_assistant_text)
            and not verification_signals(session)["verified_end"]),
    }
