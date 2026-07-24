"""Tests for shell-aware parsing and rule matching (Bash + PowerShell).

Regression for the pilot-analysis finding that 44/60 sessions used the
PowerShell tool, which the parser and the `tool: Bash` rule matchers
silently ignored.
"""

import importlib.util
from pathlib import Path

from casa.rules import Matcher, Rule, evaluate
from casa.transcript import ToolCall, _effective_command

ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    "w9_claims", ROOT / "pilot" / "analysis" / "w9_claims.py")
w9_claims = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w9_claims)


def _call(index, name, command):
    return ToolCall(index=index, name=name, input={"command": command},
                    timestamp=None, uuid=None, after_compaction=0)


def test_powershell_is_a_shell_tool():
    call = _call(0, "PowerShell", "Get-Content x.py")
    assert call.shell_command == "Get-Content x.py"
    assert call.bash_command == "Get-Content x.py"  # compat alias
    assert call.searchable_text() == "Get-Content x.py"


def test_powershell_exploration_classification():
    assert _call(0, "PowerShell", "Get-ChildItem src").is_exploration
    assert _call(0, "PowerShell", "gci -Recurse").is_exploration
    assert _call(0, "PowerShell", "Select-String -Path x -Pattern y").is_exploration
    assert not _call(0, "PowerShell", "Remove-Item x").is_exploration
    # case-insensitive, matching PowerShell semantics
    assert _call(0, "PowerShell", "GIT STATUS").is_exploration


def test_effective_command_strips_leading_cd():
    assert _effective_command('cd "a b" && pytest -q') == "pytest -q"
    assert _effective_command("Set-Location x; python check.py") == "python check.py"
    assert _effective_command("cd a && cd b && git status") == "git status"
    assert _effective_command("pytest -q") == "pytest -q"
    # cd-prefixed shell exploration now classifies correctly
    assert _call(0, "Bash", 'cd "w" && git status').is_exploration
    assert _call(0, "PowerShell", "Set-Location w; cat x.py").is_exploration


def test_shell_matcher_covers_both_shells():
    m = Matcher(tool="Shell", pattern="git commit")
    assert m.matches(_call(0, "Bash", "git commit -m x"))
    assert m.matches(_call(0, "PowerShell", "git commit -m x"))
    assert not m.matches(_call(0, "Read", "git commit"))
    exact = Matcher(tool="Bash", pattern="git commit")
    assert not exact.matches(_call(0, "PowerShell", "git commit -m x"))


def test_require_before_fires_for_powershell_commit():
    rule = Rule(id="r", type="require_before", kind="obligation",
                trigger=Matcher(tool="Shell", pattern="git commit"),
                prerequisite=Matcher(tool="Shell", pattern="pytest"))

    class FakeSession:
        tool_calls = [_call(0, "PowerShell", "git commit -m x")]

    assert [v.rule_id for v in evaluate(FakeSession(), [rule])] == ["r"]

    class OkSession:
        tool_calls = [_call(0, "PowerShell", "python -m pytest"),
                      _call(1, "PowerShell", "git commit -m x")]

    assert evaluate(OkSession(), [rule]) == []


def test_claims_success_detector():
    assert w9_claims.claims_success("All 5 tests pass and the commit is done.")
    assert w9_claims.claims_success("Done. Implemented as leapfrog.")
    # infinitive "to complete" is not a completion claim (C#11 stalled mid-work)
    assert not w9_claims.claims_success(
        "I'll wait for the background pip install to complete before running pytest.")
    assert not w9_claims.claims_success("The tests are failing on e=0.9.")
    assert not w9_claims.claims_success(None)


# --- W10: promoted core metrics -----------------------------------------

import json as _json

from casa import metrics as _m
from casa.transcript import parse as _parse

FIXTURE = ROOT / "tests" / "fixtures" / "sample_session.jsonl"


def _entry(uuid, content):
    return {"type": "assistant", "uuid": uuid,
            "timestamp": "2026-07-24T00:00:00Z",
            "message": {"role": "assistant", "model": "claude-sonnet-4-6",
                        "content": content}}


def _write_transcript(tmp_path, entries):
    path = tmp_path / "t.jsonl"
    path.write_text("\n".join(_json.dumps(e) for e in entries),
                    encoding="utf-8")
    return path


def test_final_assistant_text_tracks_last_text_message(tmp_path):
    path = _write_transcript(tmp_path, [
        _entry("a1", [{"type": "text", "text": "working on it"}]),
        _entry("a2", [{"type": "tool_use", "id": "t1", "name": "Read",
                       "input": {"file_path": "x.py"}}]),
        _entry("a3", [{"type": "text", "text": "All 3 tests pass and the "
                                               "commit is done."}]),
    ])
    session = _parse(path)
    assert session.final_assistant_text.startswith("All 3 tests pass")
    # fixture has tool_use-only assistant messages -> no final text
    assert _parse(FIXTURE).final_assistant_text is None


def test_verification_signals_and_unverified_claim(tmp_path):
    path = _write_transcript(tmp_path, [
        _entry("a1", [{"type": "tool_use", "id": "t1", "name": "Edit",
                       "input": {"file_path": "x.py", "old_string": "a",
                                 "new_string": "b"}}]),
        _entry("a2", [{"type": "tool_use", "id": "t2", "name": "PowerShell",
                       "input": {"command": "python -m pytest -q"}}]),
        _entry("a3", [{"type": "tool_use", "id": "t3", "name": "Edit",
                       "input": {"file_path": "x.py", "old_string": "b",
                                 "new_string": "c"}}]),
        _entry("a4", [{"type": "text", "text": "Done. All 3 tests pass."}]),
    ])
    session = _parse(path)
    signals = _m.verification_signals(session)
    assert signals == {"n_test_runs": 1, "tests_after_first_edit": 1,
                       "edit_test_cycles": 1, "aux_python_checks": 0,
                       "verified_end": 0}
    summary = _m.compute_all(session)
    assert summary["claims_completion"] is True
    # claimed done but never re-tested after the last edit
    assert summary["unverified_completion_claim"] is True


def test_claims_completion_core():
    assert _m.claims_completion("All 5 tests pass and the commit is done.")
    assert not _m.claims_completion(
        "I will wait for the install to complete before running pytest.")
    assert not _m.claims_completion(None)


# --- W12: tool-usage census --------------------------------------------


def _shell_call(index, name, command="echo hi"):
    from casa.transcript import ToolCall
    return ToolCall(index=index, name=name, input={"command": command},
                    timestamp=None, uuid=None, after_compaction=0)


def test_tool_census_flags_shell_like_unrecognized():
    from casa import metrics as m
    from casa.transcript import Session

    session = Session(path="x")
    session.tool_calls = [
        _shell_call(0, "Bash"),
        _shell_call(1, "PowerShell"),
        _shell_call(2, "ZshTerminal"),   # shell-like, NOT in SHELL_TOOLS
        _shell_call(3, "Read"),
    ]
    census = m.tool_census(session)
    assert census["shell_like_unrecognized"] == ["ZshTerminal"]
    assert census["tool_counts"]["PowerShell"] == 1
    assert "Bash" in census["parser_shell_tools"]


def test_tool_census_clean_when_all_recognized():
    from casa import metrics as m
    from casa.transcript import Session

    session = Session(path="x")
    session.tool_calls = [_shell_call(0, "Bash"), _shell_call(1, "PowerShell"),
                          _shell_call(2, "Read")]
    assert m.tool_census(session)["shell_like_unrecognized"] == []


def test_audit_includes_census_and_markdown_warns(tmp_path):
    import json as _json

    from casa.audit import audit_session, to_markdown

    entries = [
        {"type": "assistant", "uuid": "a1", "timestamp": "2026-07-24T00:00:00Z",
         "message": {"role": "assistant", "model": "claude-sonnet-4-6",
                     "content": [{"type": "tool_use", "id": "t1",
                                  "name": "CmdRunner",
                                  "input": {"command": "ls"}}]}},
    ]
    path = tmp_path / "t.jsonl"
    path.write_text("\n".join(_json.dumps(e) for e in entries), encoding="utf-8")
    result = audit_session(path)
    assert "census" in result
    assert result["census"]["shell_like_unrecognized"] == ["CmdRunner"]
    assert "unrecognized shell-like tools" in to_markdown(result)
