"""W9 re-examination (docs/PILOT_RESULTS.md section 7).

After the user critique that (1) wall-clock time is dominated by serving-side
confounds and (2) count-based behavior metrics are unvalidated as quality
indicators, this script re-tests the pilot claims on time-free, content-based
signals only:

- batch-shift evidence from success rates (Fisher exact) and turn/tool-call
  counts (exact Mann-Whitney), no wall time
- verification-behavior metrics (test runs, edit->test cycles, ending on a
  test) against task success

Deterministic, stdlib + casa only. Requires the local results/main/ data
(not in git); run from the repo root:

    .venv/Scripts/python.exe pilot/analysis/w9_reexam.py [results/main]
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

from casa.report import auroc, fisher_exact, mannwhitney_exact
from casa.transcript import parse


def verification_metrics(transcript_path: Path) -> dict[str, int]:
    """Content-based verification signals from one session transcript.

    A "test" is a Bash call invoking pytest; an "aux python check" is a
    non-pytest python invocation (ad-hoc numerical self-checks)."""
    session = parse(transcript_path)
    calls = session.tool_calls
    edits = [c.index for c in calls if c.is_mutation]
    first_edit = edits[0] if edits else None
    last_edit = edits[-1] if edits else None
    tests = [c.index for c in calls
             if c.name == "Bash" and "pytest" in c.bash_command]
    checks = [c.index for c in calls
              if c.name == "Bash" and "python" in c.bash_command
              and "pytest" not in c.bash_command]
    cycles = 0
    for j, e in enumerate(edits):
        nxt = edits[j + 1] if j + 1 < len(edits) else float("inf")
        if any(e < t < nxt for t in tests):
            cycles += 1
    return {
        "n_tests": len(tests),
        "tests_after_first_edit":
            sum(1 for t in tests if first_edit is not None and t > first_edit),
        "edit_test_cycles": cycles,
        "aux_python_checks": len(checks),
        "verified_end": int(bool(tests and last_edit is not None
                                 and max(tests) > last_edit)),
    }


VERIF_FEATURES = ("n_tests", "tests_after_first_edit", "edit_test_cycles",
                  "aux_python_checks", "verified_end")


def _load(task_dir: Path) -> list[dict]:
    rows = []
    for path in sorted(task_dir.glob("session-*.json")):
        row = json.loads(path.read_text(encoding="utf-8"))
        idx = row["session_index"]
        row["_ok"] = bool((row.get("grade") or {}).get("success"))
        row["_verif"] = verification_metrics(
            task_dir / f"transcript-{idx:02d}.jsonl")
        rows.append(row)
    return rows


def main(root: Path) -> None:
    print("== (1) batch-shift evidence, time-free ==")
    # C calibration numbers (1/3 success) survive only in the session log;
    # raw calibration artifacts were not retained (see PILOT_RESULTS s3).
    print(f"  C success 1/3 (calib) vs 13/15 (main): "
          f"Fisher p = {fisher_exact(1, 2, 13, 2):.3f}")
    print(f"  D success 1/7 (pre-429) vs 3/8 (post): "
          f"Fisher p = {fisher_exact(1, 6, 3, 5):.3f}")
    d_rows = _load(root / "orbit-propagator")
    pre = [r["cli"]["num_turns"] for r in d_rows if r["session_index"] <= 7]
    post = [r["cli"]["num_turns"] for r in d_rows if r["session_index"] >= 8]
    u, p = mannwhitney_exact(pre, post)
    print(f"  D num_turns pre {pre} vs post {post}: exact MW p = {p:.3f}")

    print("\n== (2) verification metrics vs success ==")
    for task in ("orbit-propagator", "rename-sweep"):
        rows = _load(root / task)
        labels = [r["_ok"] for r in rows]
        print(f"  -- {task} (fail n={sum(not y for y in labels)}) --")
        for feat in VERIF_FEATURES:
            xs = [float(r["_verif"][feat]) for r in rows]
            a = auroc(xs, labels)
            ok_m = statistics.fmean(x for x, y in zip(xs, labels) if y)
            ko_m = statistics.fmean(x for x, y in zip(xs, labels) if not y)
            print(f"    {feat:<24} AUROC {a:.3f}  "
                  f"ok mean {ok_m:.2f}  fail mean {ko_m:.2f}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("results/main"))
