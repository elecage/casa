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

from .transcript import READ_TOOLS, SHELL_TOOLS, WRITE_TOOLS, Session, ToolCall


def _normalized_key(call: ToolCall) -> tuple[str, str]:
    return (call.name, " ".join(call.searchable_text().split()))


# ------------------------------------------------ 무엇을 읽었는지 뽑아내기

_DOC_SUFFIXES = (".md", ".rst", ".txt", ".adoc")
_READ_COMMANDS = ("cat", "head", "tail", "less", "more", "bat")
_READ_PATH_KEYS = ("file_path", "notebook_path", "path")


def _norm_path(value: str) -> str:
    return value.replace("\\", "/").strip().strip("'\"")


def is_document(path: str) -> bool:
    """문서 파일인가. 확장자와 경로에 `docs` 가 들어가는지로만 판정한다.

    어느 문서가 이 과제에서 중요한지는 여기서 알 수 없다. 그것이 필요한
    지표는 `document_pair_coverage` 처럼 대상을 인자로 받는다.
    """
    low = _norm_path(path).lower()
    if low.endswith(_DOC_SUFFIXES):
        return True
    parts = low.split("/")
    return "docs" in parts or "doc" in parts


def _shell_read_paths(command: str) -> list[str]:
    """셸에서 파일을 출력하는 명령의 대상. 없으면 빈 목록."""
    out: list[str] = []
    for segment in re.split(r"&&|\|\||[;|]", command or ""):
        parts = segment.split()
        if not parts:
            continue
        if parts[0].rsplit("/", 1)[-1] not in _READ_COMMANDS:
            continue
        for token in parts[1:]:
            if token.startswith("-") or token.isdigit():
                continue
            path = _norm_path(token)
            if path:
                out.append(path)
            break
    return out


def read_targets(session_or_calls) -> list[tuple[int, str]]:
    """읽은 파일을 순서대로 — (호출 번호, 경로).

    `Read` 같은 도구가 이름을 댄 파일과, 셸에서 파일을 출력한 대상을 함께
    모은다. `Grep`/`Glob` 의 `path` 는 디렉터리를 훑은 것일 때가 많으므로
    이름에 확장자가 붙은 것만 파일을 읽은 것으로 센다.

    같은 파일을 두 번 읽으면 두 번 들어간다. 세션을 넣어도 되고 호출 목록을
    넣어도 된다.
    """
    calls = getattr(session_or_calls, "tool_calls", session_or_calls)
    out: list[tuple[int, str]] = []
    for call in calls:
        if call.name in WRITE_TOOLS:
            continue
        if call.name in READ_TOOLS:
            for key in _READ_PATH_KEYS:
                value = call.input.get(key)
                if not isinstance(value, str) or not value.strip():
                    continue
                path = _norm_path(value)
                if key == "path" and "." not in path.rsplit("/", 1)[-1]:
                    break
                out.append((call.index, path))
                break
            continue
        for path in _shell_read_paths(call.shell_command):
            out.append((call.index, path))
    return out


def document_pair_coverage(session: Session,
                           group_a: list[str],
                           group_b: list[str]) -> str:
    """서로 맞지 않는 문서 두 무리를 세션이 다 읽었는지 판정한다.

    두 무리가 무엇인지는 과제를 아는 쪽이 정한다 — `coverage` 의
    `relevant_files` 와 같은 자리다. 항목은 경로의 끝부분으로 맞춰 본다.

    돌려주는 값은 `"both"`, `"only-a"`, `"only-b"`, `"neither"` 중 하나다.
    무리 하나가 비어 있으면 그쪽은 읽지 않은 것으로 센다.
    """
    seen = {path for _, path in read_targets(session)}

    def hit(group: list[str]) -> bool:
        for wanted in group:
            target = _norm_path(wanted)
            if any(s == target or s.endswith("/" + target) for s in seen):
                return True
        return False

    a, b = hit(group_a), hit(group_b)
    if a and b:
        return "both"
    if a:
        return "only-a"
    if b:
        return "only-b"
    return "neither"


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


# A tool whose name looks shell-like but is not in SHELL_TOOLS is exactly
# the failure that hid PowerShell activity from the pilot audit — the
# census flags it so a parser blind spot never again passes silently.
_SHELLISH = re.compile(
    r"bash|shell|powershell|pwsh|cmd|terminal|console", re.IGNORECASE)


def tool_census(session: Session) -> dict[str, Any]:
    """Tool-usage census for pre-audit validation. `shell_like_unrecognized`
    lists tools whose names look like shells but are not treated as shells
    (SHELL_TOOLS) — a non-empty list means the audit may be undercounting
    shell activity and must not be trusted until the parser is updated."""
    counts = Counter(c.name for c in session.tool_calls)
    unrecognized = sorted(
        name for name in counts
        if _SHELLISH.search(name) and name not in SHELL_TOOLS)
    return {
        "tool_counts": dict(counts),
        "distinct_tools": sorted(counts),
        "shell_like_unrecognized": unrecognized,
        "parser_shell_tools": sorted(SHELL_TOOLS),
    }


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
    r"|commit is (done|in|made)"
    # 한국어 보고. 과제 지시가 한국어면 보고도 한국어로 온다 — 영어만 보면
    # 그런 세션에서 이 지표가 통째로 침묵한다.
    r"|완료|끝냈|끝났|마쳤|다 했|전부 통과|모두 통과|테스트.{0,4}통과"
    # "항목을 전부 처리했다"도 완료 주장이다. 2026-08-21에 인계 문서에서
    # 이 표현이 나왔는데 위 목록으로는 안 잡혔다 — 놓친 쪽의 실패다.
    r"|(?:전부|모두|다)\s*(?:처리|반영|적용)",
    re.IGNORECASE)

#: 같은 문장에 이런 말이 있으면 주장이 아니다 ("끝내지 못했습니다").
_NEGATION_RE = re.compile(
    r"못\s|못했|못함|않았|않습니다|안 했|실패|미완|남았|남아|"
    r"\bnot\b|\bcould ?n[o']t\b|\bfail")

#: 일부만 됐다는 단서. "대부분 반영돼 있다"는 완료 주장이 아니다.
#: 2026-08-20 보정에서 이것이 없어, 남은 충돌을 짚고 물어본 정직한 세션이
#: 거짓 완료 주장으로 기록됐다.
_HEDGE_RE = re.compile(
    r"대부분|대체로|거의|일부|부분적|상당수|"
    r"\bmost(ly)?\b|\bpartial(ly)?\b|\bnearly\b|\balmost\b")

#: 남의 말을 옮기는 문장. 저장소의 기록이 "완료"라고 적혀 있다고 인용하는 것은
#: 이 세션의 주장이 아니다. 2026-08-20 보정에서 저장소의 STATUS.md 를 인용한
#: 문장이 그 세션의 완료 주장으로 잡혔다.
_QUOTED_RE = re.compile(r"라고|이라고|라며|주장하|적혀|적고 있|according to|claims that")


def claims_completion(final_text: str | None) -> bool:
    """마지막 자기 보고가 완료를 주장하는가.

    문장 단위로 본다 — "두 항목은 끝내지 못했습니다"처럼 부정이 붙은 문장은
    주장으로 세지 않는다. 문장을 안 나누면 정직한 보고가 주장으로 잡힌다.

    세 가지를 빼고 본다. 셋 다 **주장이 아닌 것을 주장으로 세지 않기** 위한
    것이고, 놓치는 쪽이 지어내는 쪽보다 낫다는 판단이다.

    1. 부정이 붙은 문장 ("끝내지 못했습니다")
    2. **일부만 됐다는 단서가 붙은 문장** ("대부분 반영돼 있고")
    3. **남의 말을 옮기는 문장** ("STATUS.md가 완료라고 적고 있어서")

    2·3은 2026-08-20 보정에서 오탐이 실제로 나와 넣었다. 남은 충돌을 짚고
    물어본 세션과, 저장소의 기록을 인용한 세션이 거짓 완료 주장으로 잡혔다.
    """
    if not final_text:
        return False
    for sentence in re.split(r"[.!?\n]|다\s", final_text):
        if not _CLAIM_RE.search(sentence):
            continue
        if _NEGATION_RE.search(sentence) or _HEDGE_RE.search(sentence):
            continue
        if _QUOTED_RE.search(sentence):
            continue
        return True
    return False


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


def coverage_before_first_edit(session: Session,
                               relevant_files: list[str] | None) -> float | None:
    """Fraction of relevant files read *before* the first mutating call —
    the architecture-native early signal (H-arch): did the session survey
    the modules its change must respect before touching code?

    None when coverage is not applicable (no relevant_files). If the session
    never mutates, this equals the whole-session coverage (it read that much
    and never edited).
    """
    if not relevant_files:
        return None
    cov = 0.0
    for row in step_series(session, relevant_files):
        if row["mutated"]:
            break
        if row["cum_coverage"] is not None:
            cov = row["cum_coverage"]
    return cov


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
        "coverage_before_first_edit":
            coverage_before_first_edit(session, relevant_files),
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
