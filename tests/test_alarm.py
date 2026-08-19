"""Tests for the pre-registered alarm rules (docs/ALARM_RULE.md).

These tests do two jobs. They check each rule fires at the threshold it was
registered with — if a threshold drifts, a test fails loudly rather than the
change slipping through, because the whole point of pre-registration is that
tuning must be visible. And they check the alarm stays silent on a session
doing ordinary work, since the external app's only cost is a person's
attention and an alarm that always fires spends it for nothing.
"""

import pytest

from casa.alarm import THRESHOLDS, AlarmMonitor, alarm_summary
from casa.transcript import Session, ToolCall


def call(index, name, inp, result="ok", is_error=False, after_compaction=0):
    c = ToolCall(index=index, name=name, input=inp, timestamp=None, uuid=None,
                 after_compaction=after_compaction, is_error=is_error)
    c.result_text = result
    c.result_len = len(result)
    c.result_hash = f"h{index}"
    return c


def shell(index, command, **kw):
    return call(index, "Bash", {"command": command}, **kw)


def read(index, path, **kw):
    return call(index, "Read", {"file_path": path}, **kw)


def edit(index, path, old, new):
    return call(index, "Edit", {"file_path": path, "old_string": old, "new_string": new})


def session(calls):
    s = Session(path="test")
    s.tool_calls = calls
    return s


def run(calls):
    monitor = AlarmMonitor()
    return [monitor.observe(c) for c in calls]


def fired(snapshots, rule):
    return [s for s in snapshots if any(f.rule == rule for f in s.firings)]


# ------------------------------------------------------- registered values


def test_thresholds_match_the_pre_registration():
    """If this fails, a threshold moved. That must be a documented decision."""
    assert THRESHOLDS == {
        "R1_standstill": (5, 12),
        "R2_identical_calls": (3, 6),
        "R3_action_cycle": (2, 3),
        "R4_evidence_stall": (3, 6),
        "R5_error_ignored": (3, 5),
        "R6_reverts": (3, 5),
        "R7_survey_paralysis": (30, None),
    }


# ---------------------------------------------------------------- silence


def healthy():
    return [
        read(0, "a.py"), read(1, "b.py"), read(2, "c.py"), read(3, "d.py"),
        edit(4, "a.py", "x", "y"), shell(5, "pytest", result="1 failed"),
        edit(6, "b.py", "p", "q"), shell(7, "pytest", result="all passed"),
    ]


def test_ordinary_session_raises_nothing():
    assert not any(s.alerting for s in run(healthy()))


def test_warmup_suppresses_the_first_calls():
    calls = [shell(i, "pytest", result="same") for i in range(4)]
    snaps = run(calls)
    assert not any(s.alerting for s in snaps[:3]), "no history to judge on yet"


def test_compaction_suppresses_the_calls_right_after_it():
    calls = [read(i, "a.py") for i in range(8)]
    calls += [read(8, "a.py", after_compaction=1), read(9, "a.py", after_compaction=1)]
    snaps = run(calls)
    assert not snaps[8].alerting and not snaps[9].alerting


# ------------------------------------------------------------- each rule


def test_r1_standstill_alerts_at_five_and_stops_at_twelve():
    calls = [read(0, "a.py")] + [read(i, "a.py") for i in range(1, 16)]
    snaps = run(calls)
    hits = fired(snaps, "R1_standstill")
    assert hits, "repeating a look-up that teaches nothing must fire"
    first = hits[0].firings[0]
    assert first.value == 5 and first.level == "alert"
    assert any(f.level == "stop"
               for s in hits for f in s.firings if f.rule == "R1_standstill")


def test_r2_identical_calls():
    calls = [read(0, "z.py")] + [shell(i, "ls -la") for i in range(1, 8)]
    hits = fired(run(calls), "R2_identical_calls")
    assert hits and hits[0].firings[0].value >= 3


def test_r3_action_cycle():
    block = ["a.py", "b.py", "c.py"]
    calls = [read(i, block[i % 3]) for i in range(12)]
    hits = fired(run(calls), "R3_action_cycle")
    assert hits, "a repeating block of actions must fire even when varied"


def test_r4_evidence_stall_needs_an_edit_first():
    """Never checking is a different pathology than checking to no effect."""
    only_checks = [shell(i, f"pytest -k t{i}", result="3 failed") for i in range(8)]
    assert not fired(run(only_checks), "R4_evidence_stall")

    with_edit = [edit(0, "a.py", "x", "y")]
    with_edit += [shell(i, f"pytest -k t{i}", result="3 failed") for i in range(1, 8)]
    hits = fired(run(with_edit), "R4_evidence_stall")
    assert hits and hits[0].firings[0].value >= 3


def test_r4_clears_when_the_result_finally_changes():
    calls = [edit(0, "a.py", "x", "y")]
    calls += [shell(i, "pytest", result="3 failed") for i in range(1, 6)]
    calls.append(shell(6, "pytest", result="1 failed"))
    snaps = run(calls)
    assert not any(f.rule == "R4_evidence_stall" for f in snaps[-1].firings)


def test_r5_error_ignored():
    calls = [read(0, "a.py"), read(1, "b.py"), read(2, "c.py")]
    calls += [shell(i, "pytest", result="boom", is_error=True) for i in range(3, 10)]
    hits = fired(run(calls), "R5_error_ignored")
    assert hits and hits[0].firings[0].value >= 3


def test_r6_reverts():
    calls = [read(0, "a.py"), read(1, "b.py"), read(2, "c.py")]
    for i in range(3):
        calls.append(edit(3 + i * 2, "a.py", f"v{i}", f"v{i + 1}"))
        calls.append(edit(4 + i * 2, "a.py", f"v{i + 1}", f"v{i}"))
    hits = fired(run(calls), "R6_reverts")
    assert hits and hits[0].firings[0].value >= 3


def test_r7_survey_paralysis_alerts_but_never_recommends_stopping():
    """Long investigation can be legitimate; killing it is expensive."""
    calls = [read(i, f"f{i}.py") for i in range(40)]
    snaps = run(calls)
    hits = fired(snaps, "R7_survey_paralysis")
    assert hits
    assert all(f.level == "alert" for s in hits for f in s.firings
               if f.rule == "R7_survey_paralysis")


def test_r7_clears_once_something_is_edited():
    calls = [read(i, f"f{i}.py") for i in range(35)]
    calls.append(edit(35, "f0.py", "x", "y"))
    calls.append(read(36, "f99.py"))
    snaps = run(calls)
    assert not any(f.rule == "R7_survey_paralysis" for f in snaps[-1].firings)


# ------------------------------------------------------ stop recommendation


def test_two_different_rules_alerting_recommends_stopping():
    """The vote arm: no weights, so nothing to fit."""
    calls = [read(0, "a.py"), read(1, "b.py"), read(2, "c.py")]
    calls += [shell(i, "ls -la") for i in range(3, 9)]
    snaps = run(calls)
    voted = [s for s in snaps
             if len({f.rule for f in s.firings}) >= 2 and s.stop_recommended]
    assert voted


def test_single_alert_alone_does_not_recommend_stopping():
    calls = [read(0, "a.py"), read(1, "b.py"), read(2, "c.py")]
    calls += [shell(3, "ls"), shell(4, "ls"), shell(5, "ls")]
    snaps = run(calls)
    single = [s for s in snaps if len({f.rule for f in s.firings}) == 1]
    assert single
    assert all(not s.stop_recommended for s in single
               if all(f.level == "alert" for f in s.firings))


# ------------------------------------------------------------- messages


def test_messages_name_what_tripped_and_carry_the_count():
    calls = [read(0, "a.py")] + [shell(i, "ls -la") for i in range(1, 8)]
    snaps = [s for s in run(calls) if s.alerting]
    text = snaps[0].describe()
    assert any(ch.isdigit() for ch in text), "a person needs the number"
    assert "0.7" not in text, "a score is not something anyone can act on"


# -------------------------------------------------------------- summary


def test_summary_records_first_firing_even_after_it_clears():
    calls = [read(0, "a.py")] + [read(i, "a.py") for i in range(1, 8)]
    calls += [read(8, "new1.py"), read(9, "new2.py"), read(10, "new3.py")]
    out = alarm_summary(session(calls))
    assert out["ever_alerted"] is True
    assert out["tau_alert"] is not None
    assert out["alert_cleared"] is True, "recovery must be visible"


def test_summary_of_a_clean_session():
    out = alarm_summary(session(healthy()))
    assert out["ever_alerted"] is False
    assert out["tau_alert"] is None and out["tau_stop"] is None


@pytest.mark.parametrize("rule", list(THRESHOLDS))
def test_every_registered_rule_is_implemented(rule):
    """A rule in the registration with no code path is a silent omission."""
    import casa.alarm as mod

    assert rule in mod.THRESHOLDS
    source = (mod.__file__ and open(mod.__file__, encoding="utf-8").read()) or ""
    assert f'"{rule}"' in source
