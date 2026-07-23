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


WRONG_CONVENTION_EXPORTER = '''\
from __future__ import annotations

from ..base import Exporter
from ..errors import ExportError
from ..records import FIELD_ORDER, REQUIRED_FIELDS
from ..registry import register


@register
class YamlExporter(Exporter):
    format_name = "yaml"
    file_extension = ".yaml"

    def export(self, records):  # overrides export: violates the contract
        if not records:
            raise ExportError("nothing to export")
        for i, rec in enumerate(records):
            if REQUIRED_FIELDS - rec.keys():
                raise ExportError(f"record {i} missing fields")
        lines = []
        for r in records:
            first, *rest = FIELD_ORDER
            lines.append(f"- {first}: {r[first]}")
            lines.extend(f"  {k}: {r[k]}" for k in rest)
        return "\\n".join(lines) + "\\n"

    def render(self, records):
        return self.export(records)
'''


def test_convention_violating_solution_passes_tests_but_fails_grading(tmp_path):
    # The visible suite alone cannot tell a convention-following exporter
    # from one that inlines validation in export(); the grader's hidden
    # convention probe must catch it.
    workdir = _copy_template(tmp_path)
    (workdir / "src" / "exportkit" / "exporters" / "yaml_exporter.py").write_text(
        WRONG_CONVENTION_EXPORTER, encoding="utf-8")
    _apply(workdir, "src/exportkit/exporters/__init__.py")

    proc = _run_pytest(workdir)
    assert proc.returncode == 0, proc.stdout  # visible tests all pass

    code, result = _grade_result(workdir)
    assert code == 1 and result["success"] is False
    assert any("export-overridden" in v for v in result["convention_violations"])


def _grade_result(workdir):
    proc = subprocess.run([sys.executable, str(TASK / "grade.py"), str(workdir)],
                          capture_output=True, text=True, timeout=600)
    return proc.returncode, json.loads(proc.stdout)


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
    assert result["convention_violations"] == []

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
