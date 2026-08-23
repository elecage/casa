"""Behavioural badness signals (docs/BADNESS_SIGNALS.md).

Everything here answers "is this session behaving badly *right now*", using
only the session's own history — no labels, no baseline drawn from other
sessions, no task configuration. That combination is what an external app
gets: it tails one transcript from the start and has nothing to compare
against (docs/COMPARISON_RUNTIME_MONITOR.md, gaps 1 and 2).

Scope note: the catalogue lists 48 signals. This module implements the ones
computable in the field. Signals needing task configuration (which files are
relevant, which are in scope) stay in `metrics.py`, session-to-session
comparisons stay in `pilot/analysis/`, and the ones still lacking a design
are listed in STATUS.md rather than half-built here.
"""

from __future__ import annotations

import re
from typing import Any

from .metrics import (_is_aux_check, _is_test_run, _norm_path, _normalized_key,
                      is_document, read_targets)
from .progress import ProgressTracker, is_mutating_shell, normalize
from .transcript import READ_TOOLS, WRITE_TOOLS, Session, ToolCall

# --------------------------------------------------------------- 1. 헛돎


def action_cycle_length(calls: list[ToolCall], min_len: int = 3) -> int:
    """Longest repeated action block (A→B→C→A→B→C).

    Catches the thrashing that identical-call counting misses: the session
    varies its commands slightly while going nowhere.
    """
    seq = [_normalized_key(c) for c in calls]
    best = 0
    for size in range(min_len, len(seq) // 2 + 1):
        for start in range(len(seq) - 2 * size + 1):
            if seq[start:start + size] == seq[start + size:start + 2 * size]:
                best = max(best, size)
    return best


def reread_ratio(calls: list[ToolCall]) -> float:
    """Share of look-ups that asked something already asked.

    Verification calls are excluded. Re-running the same test after an edit is
    the ordinary edit-then-check cycle, not re-reading; counting it here made
    the signal fire on every healthy session, which costs the reader's
    attention and buys nothing. Whether a re-run told the session anything is
    the evidence axis's question, not this one.
    """
    seen: set[str] = set()
    lookups = repeats = 0
    for call in calls:
        if call.name in WRITE_TOOLS or is_mutating_shell(call):
            continue
        if _is_test_run(call) or _is_aux_check(call):
            continue
        lookups += 1
        key = _normalized_key(call)
        if key in seen:
            repeats += 1
        seen.add(key)
    return repeats / lookups if lookups else 0.0


def repeated_error_count(calls: list[ToolCall]) -> int:
    """Times an error text the session had already seen came back."""
    seen: set[str] = set()
    repeats = 0
    for call in calls:
        if not call.is_error or not call.result_text:
            continue
        signature = normalize(call.result_text)[:400]
        if signature in seen:
            repeats += 1
        seen.add(signature)
    return repeats


def tool_diversity_drop(calls: list[ToolCall], window: int = 10) -> float:
    """Distinct tools in the last window minus in the first, per window.

    Negative means the session narrowed to fewer kinds of action over time.
    """
    if len(calls) < 2 * window:
        return 0.0
    first = len({c.name for c in calls[:window]})
    last = len({c.name for c in calls[-window:]})
    return (last - first) / window


# ------------------------------------------------------ 2. 에러에 반응하는가


def error_response_rate(calls: list[ToolCall]) -> float | None:
    """Share of errors the session answered with a *different* action.

    The strongest single separator reported outside this project: 92% in
    succeeding trajectories against 37% in failing ones
    (docs/COMPARISON_RUNTIME_MONITOR.md). None when no error occurred.
    """
    responded = errors = 0
    for i, call in enumerate(calls[:-1]):
        if not call.is_error:
            continue
        errors += 1
        if _normalized_key(calls[i + 1]) != _normalized_key(call):
            responded += 1
    return responded / errors if errors else None


def ignored_error_count(calls: list[ToolCall]) -> int:
    """Errors answered by repeating the very same call."""
    ignored = 0
    for i, call in enumerate(calls[:-1]):
        if call.is_error and _normalized_key(calls[i + 1]) == _normalized_key(call):
            ignored += 1
    return ignored


def error_rate_trend(calls: list[ToolCall]) -> float:
    """Error rate in the last third minus the first third."""
    if len(calls) < 6:
        return 0.0
    third = len(calls) // 3
    head = sum(1 for c in calls[:third] if c.is_error) / third
    tail = sum(1 for c in calls[-third:] if c.is_error) / third
    return tail - head


# -------------------------------------------------- 4. 조사와 국소화


def survey_to_edit_ratio(calls: list[ToolCall]) -> float | None:
    """Look-ups per file change. High means walking around without building."""
    edits = sum(1 for c in calls if c.name in WRITE_TOOLS or is_mutating_shell(c))
    surveys = sum(1 for c in calls if c.is_exploration)
    return surveys / edits if edits else None


def single_file_fixation(calls: list[ToolCall]) -> float:
    """Largest share of path-bearing calls aimed at one path."""
    paths: dict[str, int] = {}
    for call in calls:
        for key in ("file_path", "path", "notebook_path"):
            value = call.input.get(key)
            if isinstance(value, str):
                norm = value.replace("\\", "/")
                paths[norm] = paths.get(norm, 0) + 1
                break
    total = sum(paths.values())
    return max(paths.values()) / total if total else 0.0


# ------------------------------------------------------- 5. 검증 행동


def first_check_index(calls: list[ToolCall]) -> int | None:
    """Call number of the first verification run; early is associated with
    success in the code-agent trajectory study."""
    for call in calls:
        if _is_test_run(call) or _is_aux_check(call):
            return call.index
    return None


def futile_check_count(session: Session) -> int:
    """Checks that changed nothing and told the session nothing new.

    28% of failing trajectories spend their tail doing exactly this.
    """
    tracker = ProgressTracker()
    futile = 0
    for call in session.tool_calls:
        verdict = tracker.observe(call)
        if (_is_test_run(call) or _is_aux_check(call)) and verdict.evidence == 0:
            futile += 1
    return futile


# ------------------------------------------- 6. 다 했다는 말과 실제의 간극

_ASSERTION = re.compile(
    r"successfully|completed|all (?:tests? )?pass|works? (?:correctly|as expected)"
    r"|verified|confirmed|done\b|fixed\b"
    r"|성공적으로|완료(?:했|됐|되었)|정상(?:적으로)? (?:동작|작동)|모두 통과|확인했",
    re.IGNORECASE,
)
_HONEST_FAILURE = re.compile(
    r"could not|couldn't|unable to|failed to|does not work|still fail|i was wrong"
    r"|하지 못했|실패했|안 됩니다|해결하지 못",
    re.IGNORECASE,
)
_STUB = re.compile(
    r"\bpass\s*$|\bNotImplementedError\b|\bTODO\b|\bFIXME\b|return None\s*$"
    r"|placeholder|dummy|mock",
    re.IGNORECASE | re.MULTILINE,
)


def assertion_density(text: str | None) -> float:
    """Confident-closing phrases per 100 words of the final self-report.

    Assertion vocabulary alone separated false success from honest failure at
    0.825 discrimination in the false-success study.
    """
    if not text:
        return 0.0
    words = max(len(text.split()), 1)
    return 100.0 * len(_ASSERTION.findall(text)) / words


def honest_failure_language(text: str | None) -> bool:
    """A session that says it failed. Reverse signal — this one is good."""
    return bool(text and _HONEST_FAILURE.search(text))


def read_heavy_tail(calls: list[ToolCall], window: int = 10) -> float:
    """Share of the last window spent reading rather than changing anything.

    Read-heavy action sequences with no state change reached 0.953
    discrimination for false success in the same study.
    """
    tail = calls[-window:] if len(calls) >= window else calls
    if not tail:
        return 0.0
    reads = sum(1 for c in tail
                if c.name in READ_TOOLS
                or (c.is_exploration and c.name not in WRITE_TOOLS))
    return reads / len(tail)


def stub_edit_count(calls: list[ToolCall]) -> int:
    """Edits whose new text is a stub — `pass`, TODO, NotImplementedError.

    Writing a placeholder and reporting completion is one of the failure
    shapes this project set out to detect.
    """
    count = 0
    for call in calls:
        if call.name not in WRITE_TOOLS:
            continue
        for key in ("new_string", "content"):
            value = call.input.get(key)
            if isinstance(value, str) and _STUB.search(value):
                count += 1
                break
    return count


# ------------------------------------------------------- 7. 재작업


def rework_ratio(calls: list[ToolCall]) -> float:
    """Share of file changes that landed on a path already changed before.

    Software-engineering churn, per session. High means the session keeps
    revisiting its own output instead of moving on.
    """
    touched: set[str] = set()
    edits = rework = 0
    for call in calls:
        if call.name not in WRITE_TOOLS:
            continue
        path = ""
        for key in ("file_path", "path", "notebook_path"):
            value = call.input.get(key)
            if isinstance(value, str):
                path = value.replace("\\", "/")
                break
        edits += 1
        if path in touched:
            rework += 1
        touched.add(path)
    return rework / edits if edits else 0.0


# --------------------------------------------------- 8. 조기 포기


_INCAPACITY = re.compile(
    r"i (?:cannot|can't|am unable to)|not possible|beyond (?:my|the) scope"
    r"|할 수 없|불가능합니다|제 권한",
    re.IGNORECASE,
)


def declares_incapacity(text: str | None) -> bool:
    return bool(text and _INCAPACITY.search(text))


def stopped_without_output(session: Session) -> bool:
    """Ended having never changed anything. Silent aborts look like this."""
    return not any(c.name in WRITE_TOOLS or is_mutating_shell(c)
                   for c in session.tool_calls)


# ------------------------------------------------------------ 9. 고착


def approach_switches(calls: list[ToolCall]) -> int:
    """Times the session changed the kind of action it was repeating.

    Zero over a long run means it never tried anything else.
    """
    kinds = [c.name for c in calls]
    return sum(1 for a, b in zip(kinds, kinds[1:]) if a != b)


def distinct_edited_paths(calls: list[ToolCall]) -> int:
    paths = set()
    for call in calls:
        if call.name not in WRITE_TOOLS:
            continue
        for key in ("file_path", "path", "notebook_path"):
            value = call.input.get(key)
            if isinstance(value, str):
                paths.add(value.replace("\\", "/"))
                break
    return len(paths)


# ------------------------- 10. 무엇을 읽었는가와 어떤 차례로 갔는가

# 여기까지의 지표는 도구 호출의 모양만 본다 — 몇 번 불렀는지, 같은 것을
# 다시 불렀는지, 에러 뒤에 무엇을 했는지. 무엇을 읽었는지와 어떤 차례로
# 갔는지는 안 본다. 이 절이 그것을 본다.
#
# 다만 어느 파일이 이 과제에서 중요한지는 여전히 안 본다. 그것을 알려면
# 과제 설정이 필요하고, 그런 지표는 `metrics.document_pair_coverage` 처럼
# 대상을 인자로 받는 쪽에 둔다.


def _first_edit_index(calls: list[ToolCall]) -> int | None:
    for call in calls:
        if call.name in WRITE_TOOLS or is_mutating_shell(call):
            return call.index
    return None


def distinct_read_paths(calls: list[ToolCall]) -> int:
    """세션이 읽은 서로 다른 파일의 수. `distinct_edited_paths` 의 읽기 쪽."""
    return len({path for _, path in read_targets(calls)})


def doc_read_ratio(calls: list[ToolCall]) -> float:
    """읽은 파일 중 문서가 차지하는 비율. 읽은 것이 없으면 0.

    코드만 읽고 적힌 것을 안 읽은 세션과 그 반대가 여기서 갈린다.
    """
    targets = read_targets(calls)
    if not targets:
        return 0.0
    return sum(1 for _, path in targets if is_document(path)) / len(targets)


def doc_before_first_edit(calls: list[ToolCall]) -> bool | None:
    """파일을 처음 바꾸기 전에 문서를 하나라도 읽었는가.

    아무 파일도 바꾸지 않은 세션은 None — 이 질문이 성립하지 않는다.
    """
    first = _first_edit_index(calls)
    if first is None:
        return None
    return any(is_document(path) for index, path in read_targets(calls)
               if index < first)


def docs_after_first_edit(calls: list[ToolCall]) -> int:
    """파일을 처음 바꾼 뒤에 문서를 읽은 횟수.

    일을 시작한 뒤 적힌 것으로 돌아가는 행위가 여기 잡힌다. 아무것도 안 바꾼
    세션은 0이다 — 돌아갈 자리가 없으므로 0과 "안 돌아갔다" 를 구별하려면
    `_first_edit_index` 를 같이 봐야 한다.
    """
    first = _first_edit_index(calls)
    if first is None:
        return 0
    return sum(1 for index, path in read_targets(calls)
               if index > first and is_document(path))


def max_reread_gap(calls: list[ToolCall]) -> int:
    """같은 파일을 다시 읽기까지 지나간 호출 수의 최대값.

    두 번 읽은 파일이 없으면 0. `reread_ratio` 는 다시 읽었다는 사실만 세고
    얼마나 뒤에 돌아왔는지는 안 센다. 바로 다음 호출에서 다시 읽는 것과
    쉰 호출 뒤에 돌아와 확인하는 것은 다른 행위다.
    """
    last: dict[str, int] = {}
    widest = 0
    for index, path in read_targets(calls):
        if path in last:
            widest = max(widest, index - last[path])
        last[path] = index
    return widest


def read_before_edit_ratio(calls: list[ToolCall]) -> float | None:
    """바꾼 파일 중 바꾸기 전에 읽어 본 것의 비율.

    아무 파일도 바꾸지 않았으면 None. 새로 만드는 파일은 읽을 것이 없으므로
    이 값을 낮추는데, 그것도 관측 대상이다 — 있는 파일을 안 읽고 덮어쓰는
    것과 구별되지 않는다는 점은 이 지표의 한계다.
    """
    first_read: dict[str, int] = {}
    for index, path in read_targets(calls):
        first_read.setdefault(path, index)
    first_edit: dict[str, int] = {}
    for call in calls:
        if call.name not in WRITE_TOOLS:
            continue
        for key in ("file_path", "path", "notebook_path"):
            value = call.input.get(key)
            if isinstance(value, str):
                first_edit.setdefault(_norm_path(value), call.index)
                break
    if not first_edit:
        return None
    looked = sum(1 for path, at in first_edit.items()
                 if path in first_read and first_read[path] < at)
    return looked / len(first_edit)


# ------------------------------------------------------------- battery


def compute_signals(session: Session) -> dict[str, Any]:
    """All field-computable badness signals for one session.

    Reported together and in full — cherry-picking the ones that came out
    well is the failure mode this battery exists to prevent
    (docs/BADNESS_SIGNALS.md, "넓히면 생기는 문제와 그 처리").
    """
    calls = session.tool_calls
    text = session.final_assistant_text
    return {
        # 1. spinning
        "action_cycle_length": action_cycle_length(calls),
        "reread_ratio": reread_ratio(calls),
        "repeated_error_count": repeated_error_count(calls),
        "tool_diversity_drop": tool_diversity_drop(calls),
        # 2. error response
        "error_response_rate": error_response_rate(calls),
        "ignored_error_count": ignored_error_count(calls),
        "error_rate_trend": error_rate_trend(calls),
        # 4. survey and localisation
        "survey_to_edit_ratio": survey_to_edit_ratio(calls),
        "single_file_fixation": single_file_fixation(calls),
        # 5. verification
        "first_check_index": first_check_index(calls),
        "futile_check_count": futile_check_count(session),
        # 6. claim vs reality
        "assertion_density": assertion_density(text),
        "honest_failure_language": honest_failure_language(text),
        "read_heavy_tail": read_heavy_tail(calls),
        "stub_edit_count": stub_edit_count(calls),
        # 7. rework
        "rework_ratio": rework_ratio(calls),
        # 8. giving up early
        "declares_incapacity": declares_incapacity(text),
        "stopped_without_output": stopped_without_output(session),
        # 9. fixation
        "approach_switches": approach_switches(calls),
        "distinct_edited_paths": distinct_edited_paths(calls),
        # 10. what was read, and in what order
        "distinct_read_paths": distinct_read_paths(calls),
        "doc_read_ratio": doc_read_ratio(calls),
        "doc_before_first_edit": doc_before_first_edit(calls),
        "docs_after_first_edit": docs_after_first_edit(calls),
        "max_reread_gap": max_reread_gap(calls),
        "read_before_edit_ratio": read_before_edit_ratio(calls),
    }
