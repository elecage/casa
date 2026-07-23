"""Tests for trajectory-level metrics (step series, sequence similarity)."""

import json
from pathlib import Path

from casa import metrics
from casa.audit import audit_session
from casa.cli import main as cli_main
from casa.transcript import parse

FIXTURE = Path(__file__).parent / "fixtures" / "sample_session.jsonl"
RELEVANT = ["/repo/a.py", "/repo/b.py"]


def test_step_series_final_row_matches_summary_metrics():
    session = parse(FIXTURE)
    series = metrics.step_series(session, relevant_files=RELEVANT)
    summary = metrics.compute_all(session, relevant_files=RELEVANT)

    assert len(series) == summary["n_tool_calls"]
    last = series[-1]
    assert last["cum_files_read"] == summary["files_read_count"]
    assert last["cum_coverage"] == summary["coverage"]
    assert last["cum_error_rate"] == summary["tool_error_rate"]


def test_step_series_is_cumulative_and_marks_first_mutation():
    session = parse(FIXTURE)
    series = metrics.step_series(session)

    for prev, cur in zip(series, series[1:]):
        assert cur["cum_exploration"] >= prev["cum_exploration"]
        assert cur["cum_errors"] >= prev["cum_errors"]

    # exploration_before_first_edit == cum_exploration at the first
    # mutated row (the Edit itself is not exploration)
    first_mutated = next(r for r in series if r["mutated"])
    assert first_mutated["cum_exploration"] == \
        metrics.exploration_before_first_edit(session)
    # coverage is None when no relevant list is given
    assert series[0]["cum_coverage"] is None


def test_tool_sequence_carries_bash_head():
    session = parse(FIXTURE)
    seq = metrics.tool_sequence(session)
    assert len(seq) == session.n_tool_calls
    assert "Bash:ls" in seq and "Bash:git" in seq
    assert "Read" in seq and "Edit" in seq


def test_normalized_edit_distance_bounds_and_known_value():
    assert metrics.normalized_edit_distance([], []) == 0.0
    assert metrics.normalized_edit_distance(["a", "b"], ["a", "b"]) == 0.0
    assert metrics.normalized_edit_distance(["a", "b", "c"], ["a", "x", "c"]) == \
        round(1 / 3, 4)
    assert metrics.normalized_edit_distance(["a"], ["x", "y"]) == 1.0


def test_prefix_divergence():
    assert metrics.prefix_divergence(["a", "b", "c"], ["a", "b", "x"]) == 2
    assert metrics.prefix_divergence(["a"], ["a"]) == 1
    assert metrics.prefix_divergence(["x"], ["y"]) == 0


def test_audit_trajectory_flag(tmp_path):
    result = audit_session(FIXTURE, trajectory=True)
    assert "trajectory" in result
    assert len(result["trajectory"]["steps"]) == result["metrics"]["n_tool_calls"]
    assert result["trajectory"]["tool_sequence"]

    # default stays lean
    assert "trajectory" not in audit_session(FIXTURE)

    # CLI wiring
    out = tmp_path / "report.json"
    code = cli_main(["audit", str(FIXTURE), "--json", "--trajectory",
                     "--out", str(out)])
    assert code == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "trajectory" in data
