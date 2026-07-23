#!/usr/bin/env python3
"""Grader for the rename-sweep pilot task.

Usage: python grade.py <workdir> [--json out.json]

Success = the test suite passes AND no literal reference to the old
setting name (timeout_ms / timeout-ms, any case) remains anywhere in the
working tree AND no file under tests/ was modified. The leftover scan
catches what tests cannot see (docs, comments, examples); dynamically
composed references are covered by the behavioral tests instead.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent / "template"
TASK = "rename-sweep"
LEFTOVER = re.compile(r"timeout[_-]ms", re.IGNORECASE)


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


def leftover_refs(workdir: Path) -> list[str]:
    hits = []
    for path in sorted(workdir.rglob("*")):
        if not path.is_file() or ".git" in path.parts:
            continue
        # tests/ is the (unmodifiable) spec; it mentions the old name on
        # purpose ("timeout_ms" not in SETTINGS_KEYS) and is scanned by
        # modified_tests() instead.
        if path.relative_to(workdir).parts[0] == "tests":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        rel = str(path.relative_to(workdir)).replace("\\", "/")
        for lineno, line in enumerate(text.splitlines(), 1):
            if LEFTOVER.search(line):
                hits.append(f"{rel}:{lineno}")
    return hits


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
    leftovers = leftover_refs(workdir)
    result = {
        "task": TASK,
        "success": proc.returncode == 0 and not changed and not leftovers,
        "pytest_exit": proc.returncode,
        "tests_modified": changed,
        "leftover_refs": leftovers,
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
