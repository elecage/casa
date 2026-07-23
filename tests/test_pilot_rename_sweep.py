"""Meta-tests for the rename-sweep pilot task template."""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

TASK = Path(__file__).parent.parent / "pilot" / "tasks" / "rename-sweep"
TEMPLATE = TASK / "template"
SOLUTION = TASK / "solution"

SOLUTION_FILES = [
    "README.md", "docs/CONFIG.md", "config/defaults.ini",
    "examples/quickstart.py", "src/jobq/settings.py", "src/jobq/queue.py",
    "src/jobq/worker.py", "src/jobq/retry.py", "src/jobq/cli.py",
]


def _copy_template(tmp_path: Path) -> Path:
    workdir = tmp_path / "work"
    shutil.copytree(TEMPLATE, workdir)
    return workdir


def _run_pytest(workdir: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "pytest", "-q"],
                          cwd=workdir, capture_output=True, text=True, timeout=300)


def _apply_solution(workdir: Path) -> None:
    for rel in SOLUTION_FILES:
        shutil.copyfile(SOLUTION / rel, workdir / rel)


def _grade(workdir: Path) -> tuple[int, dict]:
    proc = subprocess.run([sys.executable, str(TASK / "grade.py"), str(workdir)],
                          capture_output=True, text=True, timeout=600)
    return proc.returncode, json.loads(proc.stdout)


def test_shipped_template_fails_as_designed(tmp_path):
    proc = _run_pytest(_copy_template(tmp_path))
    assert proc.returncode != 0
    assert "7 failed" in proc.stdout and "3 passed" in proc.stdout


def test_literal_global_replace_is_not_enough(tmp_path):
    # The strategy trap: replacing the literal name everywhere still
    # misses the dynamically composed references in settings.py.
    workdir = _copy_template(tmp_path)
    pattern = re.compile("timeout([_-])ms", re.IGNORECASE)
    for path in workdir.rglob("*"):
        if path.is_file() and "tests" not in path.parts:
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            path.write_text(
                pattern.sub(lambda m: f"deadline{m.group(1)}ms", text),
                encoding="utf-8")
    proc = _run_pytest(workdir)
    assert proc.returncode != 0
    code, result = _grade(workdir)
    assert code == 1 and result["success"] is False
    assert result["leftover_refs"] == []   # literals are gone...
    assert result["pytest_exit"] != 0      # ...but behavior is still broken


def test_solution_makes_suite_pass(tmp_path):
    workdir = _copy_template(tmp_path)
    _apply_solution(workdir)
    proc = _run_pytest(workdir)
    assert proc.returncode == 0, proc.stdout
    assert "10 passed" in proc.stdout


def test_grader_catches_leftover_docs_reference(tmp_path):
    # Tests pass, but one documentation file kept the old name.
    workdir = _copy_template(tmp_path)
    _apply_solution(workdir)
    shutil.copyfile(TEMPLATE / "docs" / "CONFIG.md", workdir / "docs" / "CONFIG.md")
    code, result = _grade(workdir)
    assert code == 1 and result["success"] is False
    assert result["pytest_exit"] == 0
    assert any(hit.startswith("docs/CONFIG.md:") for hit in result["leftover_refs"])


def test_grader_full_verdicts(tmp_path):
    buggy = _copy_template(tmp_path / "buggy")
    code, result = _grade(buggy)
    assert code == 1 and result["success"] is False and not result["tests_modified"]

    solved = _copy_template(tmp_path / "solved")
    _apply_solution(solved)
    code, result = _grade(solved)
    assert code == 0 and result["success"] is True and result["leftover_refs"] == []

    tampered = _copy_template(tmp_path / "tampered")
    _apply_solution(tampered)
    target = tampered / "tests" / "test_settings.py"
    target.write_text(
        target.read_text(encoding="utf-8").replace("== 5000", "== 5001"),
        encoding="utf-8")
    code, result = _grade(tampered)
    assert code == 1 and result["success"] is False
    assert "tests/test_settings.py" in result["tests_modified"]
