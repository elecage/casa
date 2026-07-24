"""Tests for the main-experiment power calculation (pilot/analysis/power.py)."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    "power", ROOT / "pilot" / "analysis" / "power.py")
power = importlib.util.module_from_spec(spec)
spec.loader.exec_module(power)


def test_hanley_mcneil_var_shrinks_with_n():
    small = power.hanley_mcneil_var(0.7, 10, 10)
    large = power.hanley_mcneil_var(0.7, 50, 50)
    assert small > large > 0
    # AUC 0.5 has larger variance than an informative 0.9 at equal n
    assert power.hanley_mcneil_var(0.5, 20, 20) > power.hanley_mcneil_var(0.9, 20, 20)


def test_auroc_sessions_needed_matches_design():
    # docs/MAIN_EXPERIMENT.md section 3: ~63 sessions for a balanced task,
    # rising to ~67 at a 60% failure rate.
    assert power.auroc_sessions_needed(0.70, 0.5) == 63
    assert power.auroc_sessions_needed(0.70, 0.6) == 67
    # a stronger effect needs fewer sessions
    assert power.auroc_sessions_needed(0.80, 0.5) < 63


def test_proportion_n_needed_matches_design():
    # false-completion 0.80 vs 0.50: ~15 failed sessions one-sided,
    # ~20 two-sided (the conservative design target).
    assert power.proportion_n_needed(0.8, 0.5, one_sided=True) == 15
    assert power.proportion_n_needed(0.8, 0.5, one_sided=False) == 20
    # a smaller effect needs more samples
    assert power.proportion_n_needed(0.65, 0.5) > 15
