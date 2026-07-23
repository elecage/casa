"""Meta-tests for the orbit-propagator pilot task (hidden-oracle design)."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

TASK = Path(__file__).parent.parent / "pilot" / "tasks" / "orbit-propagator"
TEMPLATE = TASK / "template"
SOLUTION = TASK / "solution"

TEXTBOOK_RK4 = '''\
from __future__ import annotations

from .bodies import State
from .forces import accel


def euler_step(state: State, dt: float) -> State:
    ax, ay = accel(state.r)
    return State(r=(state.r[0] + state.v[0] * dt, state.r[1] + state.v[1] * dt),
                 v=(state.v[0] + ax * dt, state.v[1] + ay * dt))


def propagate(state: State, dt: float, n_steps: int) -> State:
    rx, ry = state.r
    vx, vy = state.v
    for _ in range(n_steps):
        ax1, ay1 = accel((rx, ry))
        vx2, vy2 = vx + 0.5 * dt * ax1, vy + 0.5 * dt * ay1
        ax2, ay2 = accel((rx + 0.5 * dt * vx, ry + 0.5 * dt * vy))
        vx3, vy3 = vx + 0.5 * dt * ax2, vy + 0.5 * dt * ay2
        ax3, ay3 = accel((rx + 0.5 * dt * vx2, ry + 0.5 * dt * vy2))
        ax4, ay4 = accel((rx + dt * vx3, ry + dt * vy3))
        nrx = rx + dt / 6.0 * (vx + 2 * vx2 + 2 * vx3 + (vx + dt * ax3))
        nry = ry + dt / 6.0 * (vy + 2 * vy2 + 2 * vy3 + (vy + dt * ay3))
        vx = vx + dt / 6.0 * (ax1 + 2 * ax2 + 2 * ax3 + ax4)
        vy = vy + dt / 6.0 * (ay1 + 2 * ay2 + 2 * ay3 + ay4)
        rx, ry = nrx, nry
    return State(r=(rx, ry), v=(vx, vy))
'''


def _copy_template(tmp_path: Path) -> Path:
    workdir = tmp_path / "work"
    shutil.copytree(TEMPLATE, workdir)
    return workdir


def _run_pytest(workdir: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "pytest", "-q"],
                          cwd=workdir, capture_output=True, text=True, timeout=600)


def _grade(workdir: Path) -> tuple[int, dict]:
    proc = subprocess.run([sys.executable, str(TASK / "grade.py"), str(workdir)],
                          capture_output=True, text=True, timeout=1200)
    return proc.returncode, json.loads(proc.stdout)


def _install(workdir: Path, source_text: str) -> None:
    (workdir / "src" / "orbitlib" / "integrate.py").write_text(
        source_text, encoding="utf-8")


def test_shipped_template_fails_as_designed(tmp_path):
    proc = _run_pytest(_copy_template(tmp_path))
    assert proc.returncode != 0
    assert "2 failed" in proc.stdout and "3 passed" in proc.stdout


def test_textbook_rk4_passes_visible_but_fails_contract(tmp_path):
    # The saturation blocker: a competent fixed-step RK4 clears every
    # visible test yet violates the hidden e=0.9 long-horizon contract.
    workdir = _copy_template(tmp_path)
    _install(workdir, TEXTBOOK_RK4)
    proc = _run_pytest(workdir)
    assert proc.returncode == 0, proc.stdout

    code, result = _grade(workdir)
    assert code == 1 and result["success"] is False
    assert result["pytest_exit"] == 0
    assert result["hidden_exit"] != 0


def test_solution_passes_everything(tmp_path):
    workdir = _copy_template(tmp_path)
    solution_text = (SOLUTION / "src" / "orbitlib" / "integrate.py").read_text(
        encoding="utf-8")
    _install(workdir, solution_text)
    code, result = _grade(workdir)
    assert code == 0 and result["success"] is True, result
    assert result["hidden_exit"] == 0


def test_grader_detects_test_tampering(tmp_path):
    workdir = _copy_template(tmp_path)
    solution_text = (SOLUTION / "src" / "orbitlib" / "integrate.py").read_text(
        encoding="utf-8")
    _install(workdir, solution_text)
    target = workdir / "tests" / "test_propagate.py"
    target.write_text(target.read_text(encoding="utf-8").replace("1e-3", "1e+3"),
                      encoding="utf-8")
    code, result = _grade(workdir)
    assert code == 1 and result["success"] is False
    assert "tests/test_propagate.py" in result["tests_modified"]
