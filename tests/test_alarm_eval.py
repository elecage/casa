"""Tests for the alarm evaluation script.

The script exists to judge the alarm against criteria written before it ran,
so the properties worth pinning are the ones that would quietly corrupt that
judgement: reading the graded outcome, pairing tokens with the alarm index,
and surviving sessions whose metadata is missing.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pilot" / "analysis"))

import alarm_eval  # noqa: E402


def _transcript(directory: Path, number: str, commands, tokens=40):
    """A session that repeats one command, so the alarm has something to see."""
    lines = []
    for i, command in enumerate(commands):
        lines.append(json.dumps({
            "type": "assistant",
            "timestamp": "2026-08-19T00:00:00Z",
            "message": {
                "id": f"m{i}", "model": "test",
                "usage": {"output_tokens": tokens},
                "content": [{"type": "tool_use", "id": f"t{i}", "name": "Bash",
                             "input": {"command": command}}],
            },
        }))
        lines.append(json.dumps({
            "type": "user",
            "message": {"content": [{"type": "tool_result", "tool_use_id": f"t{i}",
                                     "content": "same output"}]},
        }))
    (directory / f"transcript-{number}.jsonl").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")


def test_grade_and_tokens_are_paired_with_the_alarm(tmp_path):
    _transcript(tmp_path, "01", ["ls -la"] * 10)
    (tmp_path / "session-01.json").write_text(
        json.dumps({"grade": {"success": False}}), encoding="utf-8")

    rows = alarm_eval.load_condition(tmp_path)
    assert len(rows) == 1
    row = rows[0]
    assert row["success"] is False
    assert row["ever_alerted"] is True
    assert row["total_tokens"] == 400
    assert row["tokens_at_alert"] is not None
    assert row["tokens_after_alert"] == row["total_tokens"] - row["tokens_at_alert"]


def test_missing_metadata_leaves_success_unknown(tmp_path):
    _transcript(tmp_path, "01", ["ls -la"] * 10)
    assert alarm_eval.load_condition(tmp_path)[0]["success"] is None


def test_corrupt_metadata_does_not_raise(tmp_path):
    _transcript(tmp_path, "01", ["ls -la"] * 10)
    (tmp_path / "session-01.json").write_text("{not json", encoding="utf-8")
    assert alarm_eval.load_condition(tmp_path)[0]["success"] is None


def test_a_working_session_raises_nothing(tmp_path):
    _transcript(tmp_path, "01", [f"cat file{i}.py" for i in range(10)])
    row = alarm_eval.load_condition(tmp_path)[0]
    assert row["ever_alerted"] is False
    assert row["tokens_after_alert"] is None


def test_report_summarises_both_targets(tmp_path, capsys):
    _transcript(tmp_path, "01", ["ls -la"] * 10)
    (tmp_path / "session-01.json").write_text(
        json.dumps({"grade": {"success": True}}), encoding="utf-8")
    _transcript(tmp_path, "02", [f"cat f{i}.py" for i in range(6)])
    (tmp_path / "session-02.json").write_text(
        json.dumps({"grade": {"success": False}}), encoding="utf-8")

    out = alarm_eval.report(alarm_eval.load_condition(tmp_path))
    printed = capsys.readouterr().out
    assert out["n"] == 2
    assert out["alert_rate_success"] == 1.0
    assert out["alert_rate_failure"] == 0.0
    assert "헛경보" in printed and "비용" in printed
