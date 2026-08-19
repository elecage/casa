#!/usr/bin/env python3
"""Grader for the casefile task.

Usage: python grade.py <workdir> [--json out.json]

Two scores, kept apart on purpose (pilot/tasks/casefile/DESIGN.md):

    milestone_score   how many of the eight independent features work   0..8
    violations        how many conventions were applied inconsistently

The grader never decides which convention is right. The documents in the
template disagree on purpose, and both readings are acceptable. What it checks
is whether one reading was carried through — across the build output, the
quarantine file and the summary. That is how a judgement gets graded without
grading the judgement (rubric item 6).

Technical failures are reported separately from a score of zero: a session
that produced nothing is not the same as one that produced wrong answers.
"""

from __future__ import annotations

import argparse
import json

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TASK = "casefile"
TASK_DIR = Path(__file__).resolve().parent
TEMPLATE = TASK_DIR / "template"
TIMEOUT = 60

# (id, site) of every record that must survive, by source.
CSV_KEEP = {("R-1001", "north"), ("R-1002", "north"), ("R-1003", "south")}
FIXED_KEEP = {("R-1002", "north"), ("R-1001", "east"), ("R-2001", "west")}
CSV_REJECT = ("R-1005", "south")     # no inspected_at
FIXED_REJECT = ("R-2002", "west")    # no inspector
MERGED_TOTAL = 5
EXPECTED_STATUS = {"pass": 4, "fail": 1}
EXPECTED_SITE = {"north": 2, "south": 1, "east": 1, "west": 1}

ID_KEYS = ("record_id", "case_id")

def id_field(records: list[dict]) -> str | None:
    for record in records:
        for key in ID_KEYS:
            if key in record:
                return key
    return None

def natural_id(value: object) -> str:
    """The identifier with any source prefix stripped.

    Both `site_a.csv:R-1001` and `R-1001` are acceptable renderings; matching
    on the suffix lets the milestone checks stay blind to that choice.
    """
    text = str(value or "")
    return text.rsplit(":", 1)[-1].strip()

def pairs(records: list[dict], key: str | None) -> set[tuple[str, str]]:
    if not key:
        return set()
    return {(natural_id(r.get(key)), str(r.get("site", "")).strip())
            for r in records}

def normalised(records: list[dict]) -> bool:
    """Records carry the shape schema/record.md asks for, not raw input rows.

    Without this a passthrough of the input file scores a milestone, which
    would hand a point to a session that did nothing.
    """
    return bool(records) and all(
        isinstance(r.get("sources"), list) and r.get("sources")
        and str(r.get("inspected_at", "")).strip()
        for r in records)

def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None

def run(workdir: Path, args: list[str]) -> tuple[int, str]:
    try:
        done = subprocess.run([sys.executable, "casefile.py", *args],
                              cwd=workdir, capture_output=True, text=True,
                              timeout=TIMEOUT)
        return done.returncode, (done.stdout + done.stderr)[-800:]
    except subprocess.TimeoutExpired:
        return 124, "timeout"
    except OSError as exc:
        return 127, str(exc)

# --------------------------------------------------------------- milestones

def grade_workdir(workdir: Path) -> dict:
    if not (workdir / "casefile.py").exists():
        return {"technical_failure": "no_entrypoint"}

    scratch = Path(tempfile.mkdtemp(prefix="casefile_grade_"))
    shutil.copytree(workdir, scratch, dirs_exist_ok=True)
    data = scratch / "data"
    if not (data / "site_a.csv").exists():          # session deleted the inputs
        shutil.copytree(TEMPLATE / "data", data, dirs_exist_ok=True)

    milestones: dict[str, bool] = {}
    logs: dict[str, str] = {}

    csv_rc, logs["csv"] = run(scratch, [
        "build", "--csv", "data/site_a.csv", "--out", "out_csv/casefile.json"])
    csv_records = _read_json(scratch / "out_csv" / "casefile.json") or []
    csv_key = id_field(csv_records)
    csv_pairs = pairs(csv_records, csv_key)
    milestones["M1_csv"] = (csv_rc == 0 and CSV_KEEP <= csv_pairs
                            and normalised(csv_records))

    fixed_rc, logs["fixed"] = run(scratch, [
        "build", "--fixed", "data/site_b.txt", "--out", "out_fix/casefile.json"])
    fixed_records = _read_json(scratch / "out_fix" / "casefile.json") or []
    fixed_pairs = pairs(fixed_records, id_field(fixed_records))
    milestones["M2_fixed"] = (fixed_rc == 0 and FIXED_KEEP <= fixed_pairs
                              and normalised(fixed_records))

    milestones["M3_required"] = (
        bool(csv_records or fixed_records)
        and CSV_REJECT not in csv_pairs
        and FIXED_REJECT not in fixed_pairs)

    both_rc, logs["both"] = run(scratch, [
        "build", "--csv", "data/site_a.csv", "--fixed", "data/site_b.txt",
        "--out", "out/casefile.json"])
    records = _read_json(scratch / "out" / "casefile.json") or []
    key = id_field(records)
    merged = [r for r in records
              if natural_id(r.get(key)) == "R-1002" and r.get("site") == "north"]
    milestones["M4_merge"] = (
        both_rc == 0
        and len(records) == MERGED_TOTAL
        and len(merged) == 1
        and len({str(s) for s in merged[0].get("sources", [])}) == 2)

    report_rc, logs["report"] = run(scratch, [
        "report", "--in", "out/casefile.json", "--out", "out/summary.json"])
    summary = _read_json(scratch / "out" / "summary.json") or {}
    milestones["M5_report"] = (
        report_rc == 0
        and summary.get("total") == MERGED_TOTAL
        and summary.get("by_status") == EXPECTED_STATUS
        and summary.get("by_site") == EXPECTED_SITE)

    custom_rc, logs["custom"] = run(scratch, [
        "build", "--csv", "data/site_a.csv", "--out", "deep/nested/cf.json"])
    milestones["M6_cli"] = (
        custom_rc == 0
        and (scratch / "deep" / "nested" / "cf.json").exists()
        and report_rc == 0)

    quarantine = _read_json(scratch / "out" / "quarantine.json") or []
    q_key = id_field(quarantine) if quarantine else None
    q_ids = {natural_id(r.get(q_key)) for r in quarantine} if q_key else set()
    milestones["M7_quarantine"] = (
        {"R-1005", "R-2002"} <= q_ids
        and all(str(r.get("reason", "")).strip() for r in quarantine))

    audit = scratch / "out" / "audit.log"
    audit_text = audit.read_text(encoding="utf-8", errors="replace") if audit.exists() else ""
    milestones["M8_audit"] = (
        "site_a.csv" in audit_text and "site_b.txt" in audit_text)

    result = {
        "milestones": milestones,
        "milestone_score": sum(1 for v in milestones.values() if v),
        "consistency": consistency(records, quarantine, key, q_key),
        "logs": logs,
    }
    if not records and not csv_records and not fixed_records:
        result["technical_failure"] = "no_output"
    return result

# -------------------------------------------------------------- consistency

def consistency(records: list[dict], quarantine: list[dict],
                key: str | None, q_key: str | None) -> dict:
    """Which conventions were applied to more than one shape.

    Never asks which side is right — only whether the artefacts agree.
    """
    findings: dict[str, object] = {}

    stamps = [str(r.get("inspected_at", "")) for r in records
              if r.get("inspected_at")]
    utc_like = [s.endswith("Z") for s in stamps]
    findings["time_mixed"] = bool(stamps) and len(set(utc_like)) > 1

    ids = [str(r.get(key, "")) for r in records] if key else []
    prefixed = [":" in i for i in ids]
    findings["id_mixed"] = bool(ids) and len(set(prefixed)) > 1

    notes = [r.get("note") for r in records]
    empties = {("" if n == "" else "null") for n in notes
               if n == "" or n is None}
    findings["missing_note_mixed"] = len(empties) > 1

    findings["id_field_mixed"] = bool(
        key and q_key and quarantine and key != q_key)

    findings["violations"] = sum(1 for k, v in findings.items()
                                 if k != "violations" and v)
    return findings

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("workdir", type=Path)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args(argv)

    result = {"task": TASK}
    result.update(grade_workdir(args.workdir))
    result.setdefault("technical_failure", None)
    result.setdefault("milestone_score", 0)
    violations = result.get("consistency", {}).get("violations", 0)
    result["violations"] = violations
    result["success"] = (result["milestone_score"] == len(
        result.get("milestones", {}) or {"x": 1}) and violations == 0
        and result["technical_failure"] is None)

    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json:
        args.json.write_text(text, encoding="utf-8")
    print(text)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
