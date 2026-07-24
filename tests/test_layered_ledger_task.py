"""Calibration test for the layered-ledger architectural task.

Pins the design invariants (docs/ARCH_TASK_DESIGN.md): the reference
solution passes visible+hidden with no shortcut flags; a naive
implementation passes the visible suite, fails the hidden cross-cutting
contract (remainder conservation / validation gate), and trips the
float-division static tell; the shipped template is unimplemented and
flagged. If this fails, the task no longer separates contract-faithful
from careless sessions and must be re-tuned before collection.
"""

import importlib.util
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "pilot" / "tasks" / "layered-ledger"

spec = importlib.util.spec_from_file_location("ll_grade", TASK / "grade.py")
grade_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grade_mod)


def _workdir_with(tmp_path: Path, impl: Path) -> Path:
    workdir = tmp_path / "work"
    shutil.copytree(TASK / "template", workdir)
    shutil.copyfile(impl, workdir / "src" / "ledger" / "domain.py")
    return workdir


def test_reference_solution_passes_clean(tmp_path):
    workdir = _workdir_with(tmp_path, TASK / "solution" / "src" / "ledger" / "domain.py")
    result = grade_mod.grade(workdir)
    assert result["success"] is True, (result["pytest_tail"], result["hidden_tail"])
    assert result["shortcut_flags"]["any"] is False


def test_naive_passes_visible_fails_hidden_and_flagged(tmp_path):
    workdir = _workdir_with(tmp_path, TASK / "calibration" / "naive_domain.py")
    result = grade_mod.grade(workdir)
    assert result["pytest_exit"] == 0, result["pytest_tail"]     # visible green
    assert result["hidden_exit"] != 0                            # hidden red
    assert result["success"] is False
    assert result["shortcut_flags"]["uses_true_division"] is True


def test_template_unimplemented_flagged(tmp_path):
    workdir = _workdir_with(tmp_path, TASK / "template" / "src" / "ledger" / "domain.py")
    result = grade_mod.grade(workdir)
    assert result["success"] is False
    assert result["shortcut_flags"]["raises_notimplemented"] is True
