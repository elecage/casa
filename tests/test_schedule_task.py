"""Calibration test for the schedule ("goal clear, method not established")
task.

Pins the design invariants (pilot/tasks/schedule/README.md): the reference
(LPT + 2-opt) passes visible + hidden with no shortcut flags; plain LPT
passes the easy visible tests but misses the target on the adversarial
hidden instances; the shipped template is unimplemented and flagged. If
this fails, the task no longer separates the obvious heuristic from a
genuine improvement step and must be re-tuned before collection.
"""

import importlib.util
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "pilot" / "tasks" / "schedule"

spec = importlib.util.spec_from_file_location("sch_grade", TASK / "grade.py")
grade_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grade_mod)


def _workdir_with(tmp_path: Path, impl: Path) -> Path:
    workdir = tmp_path / "work"
    shutil.copytree(TASK / "template", workdir)
    shutil.copyfile(impl, workdir / "src" / "scheduler" / "schedule.py")
    return workdir


def test_reference_solution_passes_clean(tmp_path):
    workdir = _workdir_with(tmp_path, TASK / "solution" / "src" / "scheduler" / "schedule.py")
    result = grade_mod.grade(workdir)
    assert result["success"] is True, (result["pytest_tail"], result["hidden_tail"])
    assert result["shortcut_flags"]["any"] is False


def test_naive_lpt_passes_visible_fails_hidden(tmp_path):
    workdir = _workdir_with(tmp_path, TASK / "calibration" / "naive_schedule.py")
    result = grade_mod.grade(workdir)
    assert result["pytest_exit"] == 0, result["pytest_tail"]     # visible green
    assert result["hidden_exit"] != 0                            # hidden red
    assert result["success"] is False


def test_template_unimplemented_flagged(tmp_path):
    workdir = _workdir_with(tmp_path, TASK / "template" / "src" / "scheduler" / "schedule.py")
    result = grade_mod.grade(workdir)
    assert result["success"] is False
    assert result["shortcut_flags"]["raises_notimplemented"] is True
