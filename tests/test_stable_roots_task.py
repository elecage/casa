"""Calibration test for the stable-roots (F1) intrinsic-difficulty task.

Pins the invariant (docs/MAIN_EXPERIMENT.md, task README): the reference
solution passes visible+hidden; the naive textbook quadratic formula
passes the well-conditioned visible cases but fails the hidden precision
contract on the ill-conditioned ones. If this breaks, the task no longer
separates the obvious-but-wrong implementation from the stable one and
must be re-tuned before collection.
"""

import importlib.util
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "pilot" / "tasks" / "stable-roots"

spec = importlib.util.spec_from_file_location("sr_grade", TASK / "grade.py")
grade_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grade_mod)


def _workdir_with(tmp_path: Path, impl: Path) -> Path:
    workdir = tmp_path / "work"
    shutil.copytree(TASK / "template", workdir)
    shutil.copyfile(impl, workdir / "src" / "quadroots" / "roots.py")
    return workdir


def test_reference_solution_passes_visible_and_hidden(tmp_path):
    workdir = _workdir_with(tmp_path, TASK / "solution" / "src" / "quadroots" / "roots.py")
    result = grade_mod.grade(workdir)
    assert result["pytest_exit"] == 0, result["pytest_tail"]
    assert result["hidden_exit"] == 0, result["hidden_tail"]
    assert result["success"] is True


def test_naive_formula_passes_visible_but_fails_hidden(tmp_path):
    workdir = _workdir_with(tmp_path, TASK / "calibration" / "naive_roots.py")
    result = grade_mod.grade(workdir)
    assert result["pytest_exit"] == 0, result["pytest_tail"]
    assert result["hidden_exit"] != 0
    assert result["success"] is False


def test_unimplemented_stub_fails_visible(tmp_path):
    workdir = _workdir_with(tmp_path, TASK / "template" / "src" / "quadroots" / "roots.py")
    result = grade_mod.grade(workdir)
    assert result["success"] is False
    assert result["pytest_exit"] != 0
