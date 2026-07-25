"""Calibration test for the ml-shift (A/ML arm) distribution-shift task.

Pins the design invariants (pilot/tasks/ml-shift/README.md, docs/
ML_ARM_DESIGN.md): the reference (drops the spurious feature) clears the
held-out target; the naive pipeline (keeps it) passes the visible checks but
fails held-out; the template is unimplemented and flagged.

Skipped when scikit-learn is absent, so CI stays stdlib-clean (ML deps are
task-local). Runs locally where the deps are installed.
"""

import importlib.util
import shutil
from pathlib import Path

import pytest

pytest.importorskip("sklearn")

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "pilot" / "tasks" / "ml-shift"

spec = importlib.util.spec_from_file_location("mls_grade", TASK / "grade.py")
grade_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grade_mod)


def _workdir_with(tmp_path: Path, impl: Path | None) -> Path:
    workdir = tmp_path / "work"
    shutil.copytree(TASK / "template", workdir)
    if impl is not None:
        shutil.copyfile(impl, workdir / "solution.py")
    return workdir


def test_reference_clears_target(tmp_path):
    workdir = _workdir_with(tmp_path, TASK / "solution" / "solution.py")
    result = grade_mod.grade(workdir)
    assert result["success"] is True, result
    assert result["held_out_auroc"] >= result["tau"]
    assert result["shortcut_flags"]["any"] is False


def test_naive_passes_visible_fails_heldout(tmp_path):
    workdir = _workdir_with(tmp_path, TASK / "calibration" / "naive_solution.py")
    result = grade_mod.grade(workdir)
    assert result["pytest_exit"] == 0, result["pytest_tail"]     # valid predictions
    assert result["held_out_auroc"] < result["tau"]             # but fails held-out
    assert result["success"] is False


def test_template_unimplemented_flagged(tmp_path):
    workdir = _workdir_with(tmp_path, None)                       # shipped stub
    result = grade_mod.grade(workdir)
    assert result["success"] is False
    assert result["shortcut_flags"]["raises_notimplemented"] is True
