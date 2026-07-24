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
