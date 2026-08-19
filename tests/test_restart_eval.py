"""Tests for the restart economics analysis.

The break-even formula is the thing this project would act on, so the
properties pinned here are the ones that would make it lie: the context cost
must be the spend before the first change (a restart pays that again), and a
session that never alerted must not contribute a saving.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pilot" / "analysis"))

import restart_eval  # noqa: E402
from test_alarm_eval import _transcript  # noqa: E402


def _grade(directory: Path, number: str, success: bool) -> None:
    (directory / f"session-{number}.json").write_text(
        json.dumps({"grade": {"success": success}}), encoding="utf-8")


def test_context_cost_is_the_spend_before_the_first_change(tmp_path):
    """A restart has to pay this again; it sets the floor on any saving."""
    lines = []
    for i in range(6):
        name, inp = ("Bash", {"command": f"cat f{i}.py"})
        if i == 4:
            name, inp = "Edit", {"file_path": "a.py",
                                 "old_string": "x", "new_string": "y"}
        lines.append(json.dumps({
            "type": "assistant",
            "message": {"id": f"m{i}", "model": "t",
                        "usage": {"output_tokens": 100},
                        "content": [{"type": "tool_use", "id": f"t{i}",
                                     "name": name, "input": inp}]},
        }))
        lines.append(json.dumps({
            "type": "user",
            "message": {"content": [{"type": "tool_result",
                                     "tool_use_id": f"t{i}", "content": f"out{i}"}]},
        }))
    (tmp_path / "transcript-01.jsonl").write_text("\n".join(lines) + "\n",
                                                  encoding="utf-8")
    _grade(tmp_path, "01", True)

    row = restart_eval.enrich(tmp_path)[0]
    assert row["context_cost"] == 500, "spend up to and including the first edit"
    assert row["total_tokens"] == 600


def test_quiet_session_reports_no_saving(tmp_path):
    _transcript(tmp_path, "01", [f"cat f{i}.py" for i in range(6)])
    _grade(tmp_path, "01", True)
    row = restart_eval.enrich(tmp_path)[0]
    assert row["ever_alerted"] is False
    assert row["tokens_after_alert"] is None


def test_break_even_is_skipped_without_both_groups(tmp_path, capsys):
    _transcript(tmp_path, "01", [f"cat f{i}.py" for i in range(6)])
    _grade(tmp_path, "01", True)
    restart_eval.break_even(restart_eval.enrich(tmp_path))
    assert "표본이 부족" in capsys.readouterr().out


def test_recovery_reports_self_clearing(tmp_path, capsys):
    _transcript(tmp_path, "01", ["ls -la"] * 8 + [f"cat n{i}.py" for i in range(4)])
    _grade(tmp_path, "01", True)
    restart_eval.recovery(restart_eval.enrich(tmp_path))
    out = capsys.readouterr().out
    assert "스스로 알림이 풀린 비율" in out


def test_policies_include_the_null(tmp_path, capsys):
    """A signal that cannot beat kill-everything has contributed nothing."""
    _transcript(tmp_path, "01", ["ls -la"] * 10)
    _grade(tmp_path, "01", False)
    _transcript(tmp_path, "02", [f"cat f{i}.py" for i in range(6)])
    _grade(tmp_path, "02", True)
    restart_eval.policies(restart_eval.enrich(tmp_path))
    out = capsys.readouterr().out
    assert "전부 끊고 재시작" in out and "귀무 정책" in out
