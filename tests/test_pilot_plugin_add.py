"""Meta-tests for the plugin-add pilot task template."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

TASK = Path(__file__).parent.parent / "pilot" / "tasks" / "plugin-add"
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


def test_shipped_template_fails_as_designed(tmp_path):
    proc = _run_pytest(_copy_template(tmp_path))
    assert proc.returncode != 0
    assert "5 failed" in proc.stdout and "15 passed" in proc.stdout
    assert "test_yaml_exporter" in proc.stdout


def test_solution_makes_suite_pass(tmp_path):
    workdir = _copy_template(tmp_path)
    _apply(workdir, "src/exportkit/exporters/yaml_exporter.py",
           "src/exportkit/exporters/__init__.py")
    proc = _run_pytest(workdir)
    assert proc.returncode == 0, proc.stdout
    # contract tests parameterize over available(), so yaml joins them
    assert "23 passed" in proc.stdout


def test_forgetting_registration_import_still_fails(tmp_path):
    # The classic miss: writing the exporter without adding its import to
    # exporters/__init__.py leaves the format unregistered.
    workdir = _copy_template(tmp_path)
    _apply(workdir, "src/exportkit/exporters/yaml_exporter.py")
    proc = _run_pytest(workdir)
    assert proc.returncode != 0
    assert "test_yaml_exporter" in proc.stdout


def test_grader_verdicts(tmp_path):
    def grade(workdir):
        proc = subprocess.run([sys.executable, str(TASK / "grade.py"), str(workdir)],
                              capture_output=True, text=True, timeout=600)
        return proc.returncode, json.loads(proc.stdout)

    buggy = _copy_template(tmp_path / "buggy")
    code, result = grade(buggy)
    assert code == 1 and result["success"] is False and not result["tests_modified"]

    solved = _copy_template(tmp_path / "solved")
    _apply(solved, "src/exportkit/exporters/yaml_exporter.py",
           "src/exportkit/exporters/__init__.py")
    code, result = grade(solved)
    assert code == 0 and result["success"] is True

    tampered = _copy_template(tmp_path / "tampered")
    _apply(tampered, "src/exportkit/exporters/yaml_exporter.py",
           "src/exportkit/exporters/__init__.py")
    target = tampered / "tests" / "test_yaml_exporter.py"
    target.write_text(
        target.read_text(encoding="utf-8").replace('".yaml"', '".yml"'),
        encoding="utf-8")
    code, result = grade(tampered)
    assert code == 1 and result["success"] is False
    assert "tests/test_yaml_exporter.py" in result["tests_modified"]
