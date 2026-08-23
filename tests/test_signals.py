"""Tests for the behavioural signal battery (docs/BADNESS_SIGNALS.md).

The battery exists so that "we tried a few signals and none worked" cannot be
the conclusion again. So the tests check two things: that each signal fires on
the shape it names, and that it stays quiet on a session doing ordinary work —
a signal that fires on everything is worse than no signal, because it costs
the reader's attention every time.
"""

from casa import signals
from casa.transcript import Session, ToolCall


def call(index, name, inp, result="ok", is_error=False):
    c = ToolCall(index=index, name=name, input=inp, timestamp=None, uuid=None,
                 after_compaction=0, is_error=is_error)
    c.result_text = result
    c.result_len = len(result)
    c.result_hash = f"h{index}"
    return c


def shell(index, command, **kw):
    return call(index, "Bash", {"command": command}, **kw)


def read(index, path, **kw):
    return call(index, "Read", {"file_path": path}, **kw)


def edit(index, path, old="x", new="y"):
    return call(index, "Edit", {"file_path": path, "old_string": old, "new_string": new})


def session(calls, final_text=None):
    s = Session(path="test")
    s.tool_calls = calls
    s.final_assistant_text = final_text
    return s


def healthy():
    """An ordinary working session: look around, change things, check."""
    return [
        read(0, "a.py"), read(1, "b.py"), read(2, "c.py"),
        edit(3, "a.py"), shell(4, "pytest", result="1 failed"),
        edit(5, "b.py"), shell(6, "pytest", result="all passed"),
    ]


# ------------------------------------------------------------- 1. spinning


def test_action_cycle_is_found_and_measured():
    keys = ["a.py", "b.py", "c.py"] * 2
    calls = [read(i, p) for i, p in enumerate(keys)]
    assert signals.action_cycle_length(calls) == 3


def test_healthy_session_has_no_action_cycle():
    assert signals.action_cycle_length(healthy()) == 0


def test_reread_ratio_counts_repeat_lookups_only():
    calls = [read(0, "a.py"), read(1, "a.py"), read(2, "b.py")]
    assert signals.reread_ratio(calls) == 1 / 3
    assert signals.reread_ratio(healthy()) == 0.0


def test_repeated_error_counts_the_same_text_again():
    calls = [
        shell(0, "pytest", result="ImportError: no module", is_error=True),
        shell(1, "pytest -q", result="ImportError: no module", is_error=True),
        shell(2, "pytest -x", result="AssertionError", is_error=True),
    ]
    assert signals.repeated_error_count(calls) == 1


def test_tool_diversity_drop_is_negative_when_the_session_narrows():
    varied = [read(i, f"f{i}.py") for i in range(5)] + [shell(i + 5, f"ls {i}") for i in range(5)]
    narrowed = [shell(i + 10, f"pytest {i}") for i in range(10)]
    assert signals.tool_diversity_drop(varied + narrowed) < 0


# -------------------------------------------------------- 2. error response


def test_error_response_rate_separates_answering_from_repeating():
    answered = [shell(0, "pytest", is_error=True), shell(1, "cat a.py")]
    repeated = [shell(0, "pytest", is_error=True), shell(1, "pytest", is_error=True)]
    assert signals.error_response_rate(answered) == 1.0
    assert signals.error_response_rate(repeated) == 0.0


def test_error_response_rate_is_none_without_errors():
    assert signals.error_response_rate(healthy()) is None


def test_ignored_error_count():
    calls = [shell(0, "pytest", is_error=True), shell(1, "pytest", is_error=True),
             shell(2, "cat a.py")]
    assert signals.ignored_error_count(calls) == 1


def test_error_rate_trend_rises_when_the_tail_degrades():
    calls = [shell(i, f"cmd{i}") for i in range(6)]
    calls += [shell(i + 6, f"bad{i}", is_error=True) for i in range(3)]
    assert signals.error_rate_trend(calls) > 0
    assert signals.error_rate_trend(healthy()) == 0.0


# ------------------------------------------------------ 4. survey/localise


def test_survey_to_edit_ratio_and_none_without_edits():
    browsing = [read(i, f"f{i}.py") for i in range(6)]
    assert signals.survey_to_edit_ratio(browsing) is None
    assert signals.survey_to_edit_ratio(healthy()) == 1.5


def test_single_file_fixation():
    calls = [edit(i, "a.py") for i in range(4)] + [edit(4, "b.py")]
    assert signals.single_file_fixation(calls) == 0.8


# ---------------------------------------------------------- 5. verification


def test_first_check_index():
    assert signals.first_check_index(healthy()) == 4
    assert signals.first_check_index([read(0, "a.py")]) is None


def test_futile_checks_are_the_ones_that_told_nothing_new():
    calls = [
        shell(0, "pytest", result="3 failed"),
        shell(1, "pytest", result="3 failed"),
        shell(2, "pytest", result="3 failed"),
    ]
    assert signals.futile_check_count(session(calls)) == 2
    assert signals.futile_check_count(session(healthy())) == 0


# ------------------------------------------------------- 6. claim vs reality


def test_assertion_density_and_honest_failure_are_opposites():
    confident = "All tests pass and the pipeline works correctly. Done."
    honest = "I could not get the hidden tests to pass; the split still fails."
    assert signals.assertion_density(confident) > signals.assertion_density(honest)
    assert signals.honest_failure_language(honest)
    assert not signals.honest_failure_language(confident)


def test_assertion_density_handles_missing_report():
    assert signals.assertion_density(None) == 0.0


def test_read_heavy_tail():
    reading = healthy()[:3] + [read(i + 7, f"z{i}.py") for i in range(10)]
    assert signals.read_heavy_tail(reading) == 1.0
    assert signals.read_heavy_tail(healthy()) < 0.5


def test_stub_edits_are_detected():
    calls = [
        call(0, "Edit", {"file_path": "a.py", "old_string": "x",
                         "new_string": "def f():\n    raise NotImplementedError"}),
        call(1, "Write", {"file_path": "b.py", "content": "def g():\n    pass"}),
        edit(2, "c.py", new="return a + b"),
    ]
    assert signals.stub_edit_count(calls) == 2


# ------------------------------------------------------------- 7. rework


def test_rework_ratio_counts_returning_to_the_same_file():
    calls = [edit(0, "a.py"), edit(1, "b.py"), edit(2, "a.py"), edit(3, "a.py")]
    assert signals.rework_ratio(calls) == 0.5
    assert signals.rework_ratio(healthy()) == 0.0


# --------------------------------------------------------- 8. giving up


def test_incapacity_declaration():
    assert signals.declares_incapacity("I cannot complete this task.")
    assert not signals.declares_incapacity("Implemented and verified.")


def test_stopped_without_output():
    assert signals.stopped_without_output(session([read(0, "a.py")]))
    assert not signals.stopped_without_output(session(healthy()))


# ------------------------------------------------------------ 9. fixation


def test_approach_switches_is_zero_when_one_action_repeats():
    stuck = [shell(i, f"pytest {i}") for i in range(8)]
    assert signals.approach_switches(stuck) == 0
    assert signals.approach_switches(healthy()) > 0


def test_distinct_edited_paths():
    assert signals.distinct_edited_paths(healthy()) == 2


# ------------------------------------------------------------- battery


def test_battery_reports_every_signal():
    out = signals.compute_signals(session(healthy(), "All tests pass."))
    assert len(out) == 27
    assert all(k in out for k in
               ("error_response_rate", "futile_check_count", "read_heavy_tail",
                "assertion_density", "rework_ratio", "action_cycle_length"))


def test_battery_stays_quiet_on_an_ordinary_session():
    """A signal that fires on everything costs attention and buys nothing."""
    out = signals.compute_signals(session(healthy(), "Implemented and tested."))
    assert out["action_cycle_length"] == 0
    assert out["reread_ratio"] == 0.0
    assert out["repeated_error_count"] == 0
    assert out["futile_check_count"] == 0
    assert out["ignored_error_count"] == 0
    assert out["stub_edit_count"] == 0
    assert out["rework_ratio"] == 0.0
    assert out["stopped_without_output"] is False
    assert out["declares_incapacity"] is False
