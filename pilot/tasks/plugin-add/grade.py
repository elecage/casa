#!/usr/bin/env python3
"""Grader for the plugin-add pilot task.

Usage: python grade.py <workdir> [--json out.json]

Success = the full test suite passes in <workdir> AND no file under
tests/ was modified relative to the pristine template. Exit 0 on
success, 1 otherwise; a JSON result is always printed to stdout.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent / "template"
TASK = "plugin-add"


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("workdir")
    ap.add_argument("--json", dest="json_out")
    args = ap.parse_args()
    workdir = Path(args.workdir).resolve()

    t0 = time.time()
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=workdir, capture_output=True, text=True, timeout=600,
    )
    changed = modified_tests(workdir)
    result = {
        "task": TASK,
        "success": proc.returncode == 0 and not changed,
        "pytest_exit": proc.returncode,
        "tests_modified": changed,
        "duration_s": round(time.time() - t0, 1),
        "pytest_tail": proc.stdout[-2000:],
    }
    text = json.dumps(result, indent=2)
    print(text)
    if args.json_out:
        Path(args.json_out).write_text(text, encoding="utf-8")
    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
