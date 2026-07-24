"""Regenerate the stored audit block of collected session summaries.

The audit block inside results/<task>/session-NN.json is written at
collection time and freezes the parser/rules of that moment. After the
shell-awareness fix (docs/PILOT_RESULTS.md section 9) the stored blocks
undercount PowerShell activity and contain artifact violations, so this
script re-runs the audit from the saved transcripts and rewrites the
block in place, stamping how it was produced. Transcripts — the raw
data — are never modified.

    .venv/Scripts/python.exe pilot/analysis/reaudit.py [results/main]
"""

from __future__ import annotations

import datetime
import json
import sys
from importlib import metadata
from pathlib import Path

from casa.audit import audit_session
from casa.rules import load_rules


def rules_for(task: str, tasks_root: Path, default_rules: Path) -> Path:
    local = tasks_root / task / "canary_rules.yaml"
    return local if local.exists() else default_rules


def relevant_for(task: str, tasks_root: Path) -> list[str] | None:
    path = tasks_root / task / "relevant_files.txt"
    if not path.exists():
        return None
    return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()
            if ln.strip()]


def reaudit_dir(task_dir: Path, tasks_root: Path, default_rules: Path) -> int:
    """Rewrite audit blocks for one task directory; returns sessions updated."""
    task = task_dir.name
    rules = load_rules(rules_for(task, tasks_root, default_rules))
    relevant = relevant_for(task, tasks_root)
    try:
        version = metadata.version("casa")
    except metadata.PackageNotFoundError:
        version = None
    updated = 0
    for summary_path in sorted(task_dir.glob("session-*.json")):
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        transcript = task_dir / f"transcript-{summary['session_index']:02d}.jsonl"
        if not transcript.exists():
            print(f"  {task} #{summary['session_index']:02d}: no transcript, skipped")
            continue
        summary["audit"] = audit_session(transcript, rules=rules,
                                         relevant_files=relevant)
        summary["audit"]["reaudit"] = {
            "at": datetime.datetime.now(datetime.timezone.utc)
                  .isoformat(timespec="seconds"),
            "casa_version": version,
            "shell_aware": True,
        }
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8")
        updated += 1
    return updated


def main(root: Path) -> None:
    repo = Path(__file__).resolve().parents[2]
    tasks_root = repo / "pilot" / "tasks"
    default_rules = repo / "rules" / "canary_rules.yaml"
    for task_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        n = reaudit_dir(task_dir, tasks_root, default_rules)
        print(f"{task_dir.name}: {n} session summaries re-audited")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("results/main"))
