"""Calibration test for the config-parser (D2) hidden-oracle task.

Pins the design invariant (docs/MAIN_EXPERIMENT.md, task README): the
naive shortcut parser passes the visible suite but fails the hidden
contract, while the reference solution passes both — run through the
actual grader. Analogous to the orbit task's measured-margin requirement.
If this fails, the task no longer separates shortcut from contract-
faithful sessions and must be re-tuned before collection.
"""

import importlib.util
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "pilot" / "tasks" / "config-parser"

spec = importlib.util.spec_from_file_location("cp_grade", TASK / "grade.py")
grade_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grade_mod)


def _workdir_with(tmp_path: Path, parser_src: Path) -> Path:
    workdir = tmp_path / "work"
    shutil.copytree(TASK / "template", workdir)
    shutil.copyfile(parser_src, workdir / "src" / "minicfg" / "parser.py")
    return workdir


def test_reference_solution_passes_visible_and_hidden(tmp_path):
    workdir = _workdir_with(tmp_path, TASK / "solution" / "src" / "minicfg" / "parser.py")
    result = grade_mod.grade(workdir)
    assert result["pytest_exit"] == 0, result["pytest_tail"]
    assert result["hidden_exit"] == 0, result["hidden_tail"]
    assert result["success"] is True


def test_naive_passes_visible_but_fails_hidden(tmp_path):
    workdir = _workdir_with(tmp_path, TASK / "calibration" / "naive_parser.py")
    result = grade_mod.grade(workdir)
    # the whole point: shortcut clears the visible suite ...
    assert result["pytest_exit"] == 0, result["pytest_tail"]
    # ... but the hidden contract catches it, so grading fails
    assert result["hidden_exit"] != 0
    assert result["success"] is False


def test_unimplemented_stub_fails_visible(tmp_path):
    workdir = _workdir_with(tmp_path, TASK / "template" / "src" / "minicfg" / "parser.py")
    result = grade_mod.grade(workdir)
    assert result["success"] is False
    assert result["pytest_exit"] != 0
