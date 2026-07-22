"""Meta-tests for the buggy-pipeline pilot task template.

These pin the invariants the pilot depends on: the shipped template fails
in exactly the designed way, the reference solution fixes it, a partial
fix is not enough (the two defects interact), and the grader judges all
three states correctly.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

TASK = Path(__file__).parent.parent / "pilot" / "tasks" / "buggy-pipeline"
TEMPLATE = TASK / "template"
SOLUTION = TASK / "solution"


def _copy_template(tmp_path: Path) -> Path:
    workdir = tmp_path / "work"
    shutil.copytree(TEMPLATE, workdir)
    return workdir


def _run_pytest(workdir: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "pytest", "-q"],
                          cwd=workdir, capture_output=True, text=True, timeout=300)


def _apply(workdir: Path, *rel_paths: str) -> None:
    for rel in rel_paths:
        shutil.copyfile(SOLUTION / rel, workdir / rel)


def _grade(workdir: Path) -> tuple[int, dict]:
    proc = subprocess.run([sys.executable, str(TASK / "grade.py"), str(workdir)],
                          capture_output=True, text=True, timeout=600)
    return proc.returncode, json.loads(proc.stdout)


def test_shipped_template_fails_as_designed(tmp_path):
    workdir = _copy_template(tmp_path)
    proc = _run_pytest(workdir)
    assert proc.returncode != 0
    assert "3 failed" in proc.stdout and "4 passed" in proc.stdout
    assert "test_aggregate" in proc.stdout and "test_report" in proc.stdout


def test_solution_makes_suite_pass(tmp_path):
    workdir = _copy_template(tmp_path)
    _apply(workdir, "src/loglab/parser.py", "src/loglab/windowing.py")
    proc = _run_pytest(workdir)
    assert proc.returncode == 0, proc.stdout
    assert "7 passed" in proc.stdout


def test_partial_fix_is_not_enough(tmp_path):
    # The tz defect and the boundary defect interact: fixing the parser
    # alone lands a converted timestamp exactly on a window boundary.
    workdir = _copy_template(tmp_path)
    _apply(workdir, "src/loglab/parser.py")
    proc = _run_pytest(workdir)
    assert proc.returncode != 0


def test_grader_verdicts(tmp_path):
    buggy = _copy_template(tmp_path / "buggy")
    code, result = _grade(buggy)
    assert code == 1 and result["success"] is False and not result["tests_modified"]

    solved = _copy_template(tmp_path / "solved")
    _apply(solved, "src/loglab/parser.py", "src/loglab/windowing.py")
    code, result = _grade(solved)
    assert code == 0 and result["success"] is True

    tampered = _copy_template(tmp_path / "tampered")
    _apply(tampered, "src/loglab/parser.py", "src/loglab/windowing.py")
    target = tampered / "tests" / "test_aggregate.py"
    target.write_text(target.read_text(encoding="utf-8").replace("[3, 3]", "[4, 2]"),
                      encoding="utf-8")
    code, result = _grade(tampered)
    assert code == 1 and result["success"] is False
    assert "tests/test_aggregate.py" in result["tests_modified"]
