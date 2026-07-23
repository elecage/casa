"""Tests for the batch report aggregation (casa report)."""

import json
from pathlib import Path

from casa import report as rp
from casa.cli import main as cli_main


def test_auroc_known_values():
    assert rp.auroc([1, 2, 3, 4], [False, False, True, True]) == 1.0
    assert rp.auroc([4, 3, 2, 1], [False, False, True, True]) == 0.0
    assert rp.auroc([1, 1, 1, 1], [False, False, True, True]) == 0.5
    assert rp.auroc([1, 2], [True, True]) is None
    # pos={2,4} vs neg={1,3}: 3 of 4 pairs concordant
    assert rp.auroc([1, 2, 3, 4], [False, True, False, True]) == 0.75


def test_pooled_auroc_weights_by_pairs():
    g1 = ([1, 2], [False, True])            # 1 pair, win
    g2 = ([5, 4, 3, 6], [True, False, False, True])  # 4 pairs, 3 wins... compute
    pooled = rp.pooled_auroc([g1, g2])
    # g2 pos=[5,6] neg=[4,3]: wins 5>4,5>3,6>4,6>3 = 4 -> total (1+4)/5
    assert pooled == 1.0
    g3 = ([2, 1], [True, False])
    assert rp.pooled_auroc([([1, 2], [True, False]), g3]) == 0.5


def test_logistic_calibration_sanity():
    xs = [0.0, 0.1, 0.2, 0.3, 0.7, 0.8, 0.9, 1.0] * 3
    labels = ([False] * 4 + [True] * 4) * 3
    probs = rp.logistic_loo_probs(xs, labels)
    assert probs is not None
    assert rp.brier(probs, labels) < 0.1
    assert 0.0 <= rp.ece(probs, labels) <= 1.0
    assert rp.logistic_loo_probs([1.0, 2.0, 3.0, 4.0], [True] * 4) is None


def test_heuristic_flag():
    assert rp.heuristic_flag({"audit": {"metrics":
        {"exploration_before_first_edit": 0, "max_repetition": 1}}})
    assert rp.heuristic_flag({"audit": {"metrics":
        {"exploration_before_first_edit": 5, "max_repetition": 3}}})
    assert rp.heuristic_flag({"audit": {
        "metrics": {"exploration_before_first_edit": 5, "max_repetition": 1},
        "violations": [{"rule_id": "canary-test-before-commit"}]}})
    assert not rp.heuristic_flag({"audit": {"metrics":
        {"exploration_before_first_edit": 5, "max_repetition": 1},
        "violations": []}})


def _tool_use(name, input_, ts="2026-07-23T00:00:00Z"):
    return {"type": "assistant", "timestamp": ts,
            "message": {"model": "m", "content": [
                {"type": "tool_use", "id": "t", "name": name, "input": input_}]}}


def _write_session(result_dir: Path, index: int, task: str, success: bool,
                   calls: list[dict], explore: int) -> None:
    transcript = result_dir / f"transcript-{index:02d}.jsonl"
    transcript.write_text("\n".join(json.dumps(c) for c in calls) + "\n",
                          encoding="utf-8")
    summary = {
        "task": task, "session_index": index, "wall_s": 60.0 + index,
        "cli": {"total_cost_usd": 0.2},
        "transcript": str(transcript),
        "audit": {"metrics": {"exploration_before_first_edit": explore,
                              "coverage": 0.5, "n_tool_calls": len(calls),
                              "max_repetition": 1},
                  "violations": []},
        "grade": {"success": success},
    }
    (result_dir / f"session-{index:02d}.json").write_text(
        json.dumps(summary), encoding="utf-8")


def _make_batch(tmp_path: Path) -> tuple[Path, Path]:
    tasks_root = tmp_path / "tasks"
    (tasks_root / "taskx").mkdir(parents=True)
    (tasks_root / "taskx" / "relevant_files.txt").write_text(
        "/r/a.py\n/r/b.py\n", encoding="utf-8")

    result_dir = tmp_path / "results" / "taskx"
    result_dir.mkdir(parents=True)
    explorer = [_tool_use("Read", {"file_path": "/r/a.py"}),
                _tool_use("Read", {"file_path": "/r/b.py"}),
                _tool_use("Grep", {"pattern": "x"}),
                _tool_use("Edit", {"file_path": "/r/a.py"})]
    rusher = [_tool_use("Edit", {"file_path": "/r/a.py"}),
              _tool_use("Bash", {"command": "python -m pytest"})]
    # successes explore more: AUROC on cum_exploration should be high
    _write_session(result_dir, 1, "taskx", True, explorer, explore=3)
    _write_session(result_dir, 2, "taskx", True, explorer, explore=3)
    _write_session(result_dir, 3, "taskx", False, rusher, explore=0)
    _write_session(result_dir, 4, "taskx", False, rusher, explore=0)
    return result_dir, tasks_root


def test_build_report_end_to_end(tmp_path):
    result_dir, tasks_root = _make_batch(tmp_path)
    report = rp.build_report([result_dir], tasks_root=tasks_root,
                             k_grid=(1, 2, 4))
    assert report["n_sessions"] == 4
    task = report["tasks"]["taskx"]
    assert task["successes"] == 2 and task["success_rate"] == 0.5

    # at k=2 the explorers have read 2 relevant files, rushers 0
    pooled = report["auroc_at_k"]["cum_exploration"]["pooled"]
    assert pooled["2"] == 1.0
    coverage_pooled = report["auroc_at_k"]["cum_coverage"]["pooled"]
    assert coverage_pooled["2"] == 1.0

    # heuristic flags exactly the two edit-first sessions
    heuristic = report["baselines"]["simple_heuristic"]
    assert heuristic["flagged"] == 2
    assert heuristic["flag_precision_for_failure"] == 1.0
    assert heuristic["failure_recall"] == 1.0
    assert heuristic["auroc"] == 1.0

    markdown = rp.report_to_markdown(report)
    assert "taskx" in markdown and "AUROC@k" in markdown


def test_report_cli(tmp_path):
    result_dir, tasks_root = _make_batch(tmp_path)
    out = tmp_path / "batch.json"
    code = cli_main(["report", str(result_dir), "--tasks-root", str(tasks_root),
                     "--k-grid", "1,2,4", "--json", "--out", str(out)])
    assert code == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["n_sessions"] == 4
