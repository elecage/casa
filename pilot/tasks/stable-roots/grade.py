#!/usr/bin/env python3
"""Grader for the stable-roots pilot task.

Usage: python grade.py <workdir> [--json out.json]

Success = visible suite passes AND tests/ unmodified AND the hidden
precision-contract suite passes. The hidden suite (never shipped) blocks
iterate-until-green: the naive textbook formula clears the visible cases
but cancels on the ill-conditioned hidden ones.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

TASK_DIR = Path(__file__).resolve().parent
TEMPLATE = TASK_DIR / "template"
HIDDEN = TASK_DIR / "hidden_tests"
TASK = "stable-roots"


def _norm(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def modified_tests(workdir: Path) -> list[str]:
    changed = []
    for src in sorted((TEMPLATE / "tests").rglob("*")):
        if not src.is_file():
            continue
        rel = src.relative_to(TEMPLATE)
        dst = workdir / rel
        if not dst.exists() or _norm(dst.read_bytes()) != _norm(src.read_bytes()):
            changed.append(str(rel).replace("\\", "/"))
    return changed


def run_visible(workdir: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=workdir, capture_output=True, text=True, timeout=300,
    )


def run_hidden(workdir: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(workdir / "src")
    return subprocess.run(
        [sys.executable, "-m", "pytest", str(HIDDEN), "-q", "-p", "no:cacheprovider"],
        cwd=TASK_DIR, capture_output=True, text=True, timeout=300, env=env,
    )


def grade(workdir: Path) -> dict:
    t0 = time.time()
    visible = run_visible(workdir)
    changed = modified_tests(workdir)
    hidden = run_hidden(workdir)
    return {
        "task": TASK,
        "success": visible.returncode == 0 and not changed and hidden.returncode == 0,
        "pytest_exit": visible.returncode,
        "hidden_exit": hidden.returncode,
        "tests_modified": changed,
        "duration_s": round(time.time() - t0, 1),
        "pytest_tail": visible.stdout[-1500:],
        "hidden_tail": hidden.stdout[-1500:],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("workdir")
    ap.add_argument("--json", dest="json_out")
    args = ap.parse_args()
    result = grade(Path(args.workdir).resolve())
    text = json.dumps(result, indent=2)
    print(text)
    if args.json_out:
        Path(args.json_out).write_text(text, encoding="utf-8")
    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
