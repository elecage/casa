"""Tests for pilot/analysis/signal_validation.py (pure functions)."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "signal_validation", ROOT / "pilot" / "analysis" / "signal_validation.py")
sv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sv)


def test_auroc_known_values():
    assert sv.auroc([1, 2, 3], [0]) == 1.0        # all positives higher
    assert sv.auroc([0], [1, 2, 3]) == 0.0        # all lower
    assert sv.auroc([1], [1]) == 0.5              # tie
    assert sv.auroc([], [1]) is None


def _row(success, claims, **metrics):
    return {"grade": {"success": success},
            "audit": {"metrics": {"claims_completion": claims, **metrics}}}


def test_completion_split_uses_only_claim_done():
    rows = [
        _row(True, True, n_test_runs=5),      # true completion
        _row(False, True, n_test_runs=1),     # false completion
        _row(False, False, n_test_runs=9),    # not a claim -> excluded
    ]
    tv, fv = sv.completion_split(rows, "n_test_runs")
    assert tv == [5] and fv == [1]


def test_completion_split_skips_missing_metric():
    rows = [_row(True, True), _row(False, True, n_test_runs=2)]
    tv, fv = sv.completion_split(rows, "n_test_runs")
    assert tv == [] and fv == [2]


def test_cost_spread():
    rows = [
        {"grade": {"success": True}, "cli": {"total_cost_usd": 1.0}},
        {"grade": {"success": True}, "cli": {"total_cost_usd": 2.0}},
        {"grade": {"success": False}, "cli": {"total_cost_usd": 9.0}},  # excluded
    ]
    sp = sv.cost_spread(rows)
    assert sp["n"] == 2 and sp["ratio"] == 2.0 and sp["max"] == 2.0


def test_cost_spread_needs_two_successes():
    assert sv.cost_spread([{"grade": {"success": True}, "cli": {"total_cost_usd": 1.0}}]) is None


def test_spearman_monotonic():
    assert sv.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == 1.0
    assert sv.spearman([1, 2, 3, 4], [40, 30, 20, 10]) == -1.0
    # rank correlation ignores non-linearity as long as order is preserved
    assert sv.spearman([1, 2, 3, 4], [1, 4, 9, 16]) == 1.0


def test_spearman_guards():
    assert sv.spearman([1, 2, 3], [1, 2, 3]) is None       # < min_n
    assert sv.spearman([1, 1, 1, 1], [1, 2, 3, 4]) is None  # no variance
    # non-numeric pairs are dropped
    assert sv.spearman([1, 2, 3, 4, None], [1, 2, 3, 4, 5]) == 1.0


def test_outcome_series():
    rows = [
        {"grade": {"success": True}, "cli": {"total_cost_usd": 1.5},
         "audit": {"violations": [{}, {}]}},
        {"grade": {"success": False}, "cli": {"total_cost_usd": 0.5},
         "audit": {"violations": []}},
    ]
    assert sv.outcome_series(rows, "success") == [1, 0]
    assert sv.outcome_series(rows, "cost") == [1.5, 0.5]
    assert sv.outcome_series(rows, "violations") == [2, 0]
