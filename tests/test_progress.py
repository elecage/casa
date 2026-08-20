"""Tests for the three-way progress rule (docs/PROGRESS_RULE.md).

Each test pins a property that, if it broke, would make the rule report the
opposite of the truth:

1. normalization must erase elapsed time but keep counts. Blurring digits
   turns "3 failed, 5 passed" into a constant and the evidence axis dies.
2. re-reading must not count, but re-reading a file that *changed* must —
   otherwise editing then verifying reads as standing still.
3. an edit that undoes an earlier edit must score -1, not 0. Thrashing back
   and forth is invisible at 0.
4. "repairing the wrong problem" must show as artifact rising while evidence
   stays flat. This is the shape the whole design exists to catch.
5. compaction must reset the knowledge memory only. The session legitimately
   forgot what it read; the files on disk did not change.
"""

from casa.progress import (
    ProgressTracker,
    is_mutating_shell,
    normalize,
    progress_summary,
)
from casa.transcript import ToolCall


def call(index, name, inp, result="", is_error=False, after_compaction=0):
    c = ToolCall(index=index, name=name, input=inp, timestamp=None, uuid=None,
                 after_compaction=after_compaction, is_error=is_error)
    if result is not None:
        c.result_text = result
        c.result_len = len(result)
        c.result_hash = f"h{hash(result)}"
    return c


def shell(index, command, **kw):
    return call(index, "Bash", {"command": command}, **kw)


def read(index, path, result="body", **kw):
    return call(index, "Read", {"file_path": path}, result=result, **kw)


class FakeSession:
    def __init__(self, calls):
        self.tool_calls = calls


# ------------------------------------------------------------- normalize


def test_normalize_erases_elapsed_time():
    a = "3 failed, 5 passed in 1.23s"
    b = "3 failed, 5 passed in 44.10s"
    assert normalize(a) == normalize(b)


def test_normalize_keeps_counts():
    """The whole evidence axis rests on this."""
    assert normalize("3 failed, 5 passed") != normalize("2 failed, 6 passed")


def test_normalize_erases_timestamps_and_addresses():
    assert normalize("at 2026-08-19T09:39:54Z ok") == normalize("at 2026-01-01T00:00:00Z ok")
    assert normalize("obj at 0xdeadbeef") == normalize("obj at 0x1234")


# --------------------------------------------------------------- knowledge


def test_first_read_is_knowledge_and_reread_is_not():
    t = ProgressTracker()
    assert t.observe(read(0, "a.py")).knowledge == 1
    second = t.observe(read(1, "a.py"))
    assert second.knowledge == 0 and second.is_standstill


def test_reread_of_changed_file_is_knowledge():
    """Edit then read-back must not look like standing still."""
    t = ProgressTracker()
    t.observe(read(0, "a.py", result="before"))
    again = t.observe(read(1, "a.py", result="after"))
    assert again.knowledge == 1 and again.reason == "changed-lookup"


def test_first_error_is_knowledge_and_repeat_error_is_not():
    t = ProgressTracker()
    first = t.observe(shell(0, "ruff check", result="E501 line too long", is_error=True))
    assert first.knowledge == 1 and first.reason == "new-error"
    repeat = t.observe(shell(1, "ruff check", result="E501 line too long", is_error=True))
    assert repeat.knowledge == 0


def test_same_error_after_a_different_command_still_counts_as_seen():
    t = ProgressTracker()
    t.observe(shell(0, "ruff check", result="boom", is_error=True))
    other = t.observe(shell(1, "ruff check src", result="boom", is_error=True))
    assert other.knowledge == 0, "the error is the information, not the command"


# ---------------------------------------------------------------- artifact


def test_new_edit_is_artifact_gain():
    t = ProgressTracker()
    v = t.observe(call(0, "Edit", {"file_path": "a.py",
                                   "old_string": "x", "new_string": "y"}))
    assert v.artifact == 1 and v.reason == "new-content"


def test_no_op_edit_scores_zero():
    t = ProgressTracker()
    v = t.observe(call(0, "Edit", {"file_path": "a.py",
                                   "old_string": "x", "new_string": "x"}))
    assert v.artifact == 0 and v.reason == "no-op-edit"


def test_revert_scores_minus_one():
    """Thrashing is invisible if undoing counts as 0."""
    t = ProgressTracker()
    t.observe(call(0, "Edit", {"file_path": "a.py",
                               "old_string": "x", "new_string": "y"}))
    back = t.observe(call(1, "Edit", {"file_path": "a.py",
                                      "old_string": "y", "new_string": "x"}))
    assert back.artifact == -1 and back.reason == "revert"


def test_revert_is_path_scoped():
    t = ProgressTracker()
    t.observe(call(0, "Edit", {"file_path": "a.py",
                               "old_string": "x", "new_string": "y"}))
    other = t.observe(call(1, "Edit", {"file_path": "b.py",
                                       "old_string": "y", "new_string": "x"}))
    assert other.artifact == 1, "a different file is not an undo"


def test_multiedit_counts_as_a_gain_if_any_part_is_new():
    t = ProgressTracker()
    v = t.observe(call(0, "MultiEdit", {"file_path": "a.py", "edits": [
        {"old_string": "x", "new_string": "x"},
        {"old_string": "p", "new_string": "q"},
    ]}))
    assert v.artifact == 1


def test_shell_write_counts_but_lowers_state_confidence():
    t = ProgressTracker()
    t.observe(call(0, "Edit", {"file_path": "a.py",
                               "old_string": "x", "new_string": "y"}))
    v = t.observe(shell(1, "sed -i s/a/b/ a.py"))
    assert v.artifact == 1 and v.reason == "shell-write"
    assert t.state_confidence == 0.5


def test_shell_write_marks_the_touched_path_untrusted():
    """After an opaque write we cannot claim to know the file's state."""
    t = ProgressTracker()
    t.observe(call(0, "Edit", {"file_path": "a.py",
                               "old_string": "x", "new_string": "y"}))
    t.observe(shell(1, "sed -i s/y/x/ a.py"))
    back = t.observe(call(2, "Edit", {"file_path": "a.py",
                                      "old_string": "y", "new_string": "x"}))
    assert back.artifact == 1, "revert claims are suppressed on untracked paths"


def test_failed_shell_write_is_not_a_gain():
    t = ProgressTracker()
    v = t.observe(shell(0, "rm nope.txt", result="No such file", is_error=True))
    assert v.artifact == 0


# ---------------------------------------------------------------- evidence


def test_first_check_is_evidence_and_identical_rerun_is_not():
    t = ProgressTracker()
    first = t.observe(shell(0, "pytest", result="3 failed in 1.0s"))
    assert first.evidence == 1
    same = t.observe(shell(1, "pytest", result="3 failed in 9.9s"))
    assert same.evidence == 0 and same.is_standstill, "only the clock changed"


def test_changed_check_is_evidence():
    t = ProgressTracker()
    t.observe(shell(0, "pytest", result="3 failed"))
    better = t.observe(shell(1, "pytest", result="1 failed"))
    assert better.evidence == 1 and better.reason == "new-check-result"


def test_varying_the_check_command_does_not_manufacture_evidence():
    """Evidence is keyed on the result, not the command.

    Keying on the command let a session change its `-k` selector each round,
    collect the same answer every time, and score fresh evidence on each —
    the same hole already closed on the error axis.
    """
    t = ProgressTracker()
    verdicts = [t.observe(shell(i, f"pytest -k t{i}", result="3 failed"))
                for i in range(4)]
    assert [v.evidence for v in verdicts] == [1, 0, 0, 0]


# ------------------------------------------------ the shape we exist to catch


def test_repairing_the_wrong_problem_shows_as_artifact_without_evidence():
    """Edits keep landing, the test keeps saying the same thing.

    Every single-axis definition of progress calls this productive.
    """
    calls = [shell(0, "pytest", result="3 failed")]
    for i in range(1, 7):
        calls.append(call(i * 2 - 1, "Edit",
                          {"file_path": "a.py",
                           "old_string": f"v{i}", "new_string": f"v{i + 1}"}))
        calls.append(shell(i * 2, "pytest", result="3 failed"))

    summary = progress_summary(FakeSession(calls))
    assert summary["artifact_gains"] == 6
    assert summary["evidence_gains"] == 1, "only the very first run was news"


def test_spinning_run_length_is_reported():
    calls = [read(0, "a.py")] + [read(i, "a.py") for i in range(1, 6)]
    summary = progress_summary(FakeSession(calls))
    assert summary["longest_standstill_run"] == 5
    assert summary["progress_density"] < 0.2


# -------------------------------------------------------------- compaction


def test_compaction_resets_knowledge_but_not_artifact_or_evidence():
    t = ProgressTracker()
    t.observe(read(0, "a.py"))
    t.observe(call(1, "Edit", {"file_path": "a.py",
                               "old_string": "x", "new_string": "y"}))
    t.observe(shell(2, "pytest", result="3 failed"))

    again = t.observe(read(3, "a.py", after_compaction=1))
    assert again.knowledge == 1, "the session legitimately forgot"

    same_check = t.observe(shell(4, "pytest", result="3 failed", after_compaction=1))
    assert same_check.evidence == 0, "the test result did not change"

    undo = t.observe(call(5, "Edit", {"file_path": "a.py",
                                      "old_string": "y", "new_string": "x"},
                          after_compaction=1))
    assert undo.artifact == -1, "the file is real whether or not it is remembered"


# ------------------------------------------------------- shell classification


def test_mutating_shell_detection():
    assert is_mutating_shell(shell(0, "rm -rf build"))
    assert is_mutating_shell(shell(0, "sed -i s/a/b/ f.py"))
    assert is_mutating_shell(shell(0, "echo hi > out.txt"))
    assert is_mutating_shell(shell(0, "git commit -m x"))


def test_read_only_and_stream_merge_are_not_mutations():
    assert not is_mutating_shell(shell(0, "cat f.py"))
    assert not is_mutating_shell(shell(0, "git status"))
    assert not is_mutating_shell(shell(0, "pytest -q 2>&1"))
    assert not is_mutating_shell(shell(0, "grep -n x f.py"))


def test_angle_bracket_inside_quotes_is_not_a_redirect():
    """Regression, found on real sessions.

    87 of 90 calls flagged as writes were analysis snippets whose Python code
    contained a comparison. Scoring them as artifact instead of evidence
    inverts the exact pattern the three-way rule is built to see.
    """
    analysis = 'python -c "import pandas as pd; print((df.s > 0).mean())"'
    assert not is_mutating_shell(shell(0, analysis))
    assert not is_mutating_shell(shell(0, 'pytest -k "value > 1"'))
    # `git commit` stays a write — it is on the explicit list, quotes or not.
    assert is_mutating_shell(shell(0, 'git commit -m "fixes a > b case"'))


def test_real_redirect_outside_quotes_is_still_a_write():
    assert is_mutating_shell(shell(0, 'python gen.py > predictions.csv'))
    assert is_mutating_shell(shell(0, 'echo "a > b" > out.txt'))


def test_analysis_snippet_scores_on_the_evidence_axis():
    t = ProgressTracker()
    v = t.observe(shell(0, 'python -c "print((df.s > 0).mean())"', result="0.51"))
    assert v.evidence == 1 and v.artifact == 0


def test_write_revert_is_detected_by_content_hash():
    """Write replaces the whole file, so the edit-pair heuristic is blind here.

    Every Write looks like ("", content) and no inverse pair ever appears, so
    without hashing the content a session that writes A, then B, then A again
    scores three gains and no thrashing.
    """
    t = ProgressTracker()
    first = t.observe(call(0, "Write", {"file_path": "a.py", "content": "A"}))
    second = t.observe(call(1, "Write", {"file_path": "a.py", "content": "B"}))
    back = t.observe(call(2, "Write", {"file_path": "a.py", "content": "A"}))
    assert [first.artifact, second.artifact, back.artifact] == [1, 1, -1]


def test_rewriting_identical_content_is_a_no_op():
    t = ProgressTracker()
    t.observe(call(0, "Write", {"file_path": "a.py", "content": "A"}))
    again = t.observe(call(1, "Write", {"file_path": "a.py", "content": "A"}))
    assert again.artifact == 0 and again.reason == "no-op-edit"


def test_write_revert_is_path_scoped():
    t = ProgressTracker()
    t.observe(call(0, "Write", {"file_path": "a.py", "content": "A"}))
    t.observe(call(1, "Write", {"file_path": "a.py", "content": "B"}))
    other = t.observe(call(2, "Write", {"file_path": "b.py", "content": "A"}))
    assert other.artifact == 1


def test_null_device_redirects_are_not_writes():
    """`2>/dev/null` 은 파일을 쓰는 것이 아니다.

    2026-08-20 프로브에서 드러났다 — `ls ... 2>/dev/null` 같은 조사 호출이
    산출물 진전으로 세어지고 있었다. 스냅숏 수와 "파일 바꾼 호출 수"가 안
    맞아서 잡혔다.
    """
    from casa.progress import is_mutating_shell
    from casa.transcript import ToolCall

    def bash(command):
        call = ToolCall(index=0, name="Bash", input={"command": command},
                        timestamp=None, uuid=None, after_compaction=0,
                        is_error=False)
        call.result_text, call.result_len, call.result_hash = "", 0, "h"
        return call

    assert not is_mutating_shell(bash("ls x 2>/dev/null"))
    assert not is_mutating_shell(bash('grep -r "p" x -l 2>/dev/null'))
    assert not is_mutating_shell(bash("dir 2>nul"))
    # 진짜 파일 쓰기는 그대로 잡힌다.
    assert is_mutating_shell(bash("python x.py > out.csv"))
    assert is_mutating_shell(bash("echo hi >> log.txt"))
