"""W9 addendum: claim-vs-reality audit (docs/PILOT_RESULTS.md section 9).

The user's core complaint about session variance includes sessions that
CLAIM completion while the work is incomplete (missing module, mock
implementation, unmet contract). This script cross-tabulates each
session's final self-report against the graded outcome, and re-audits
canary-rule violations with the shell-aware parser (Bash + PowerShell).

Deterministic. The success-claim detector is a regex over the final
message; it flags explicit completion assertions only.

    .venv/Scripts/python.exe pilot/analysis/w9_claims.py [results/main]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from casa.metrics import claims_completion
from casa.rules import evaluate, load_rules
from casa.transcript import parse

TASKS = ("buggy-pipeline", "plugin-add", "rename-sweep", "orbit-propagator")


def claims_success(final_text: str | None) -> bool:
    """Alias for casa.metrics.claims_completion (promoted to core in W10)."""
    return claims_completion(final_text)


def rules_for(task: str, tasks_root: Path, default_rules: Path) -> Path:
    local = tasks_root / task / "canary_rules.yaml"
    return local if local.exists() else default_rules


def main(root: Path) -> None:
    repo = Path(__file__).resolve().parents[2]
    tasks_root = repo / "pilot" / "tasks"
    default_rules = repo / "rules" / "canary_rules.yaml"

    print("== claim-vs-reality (final self-report vs graded outcome) ==")
    counts = {("claim", True): 0, ("claim", False): 0,
              ("noclaim", True): 0, ("noclaim", False): 0}
    for task in TASKS:
        for sf in sorted((root / task).glob("session-*.json")):
            d = json.loads(sf.read_text(encoding="utf-8"))
            ok = bool((d.get("grade") or {}).get("success"))
            claim = claims_success((d.get("cli") or {}).get("result"))
            counts[("claim" if claim else "noclaim", ok)] += 1
            if claim and not ok:
                print(f"  FALSE COMPLETION  {task} #{d['session_index']:02d}")
            if not claim:
                print(f"  no completion claim: {task} #{d['session_index']:02d} "
                      f"(success={ok})")
    print(f"  claimed done & succeeded: {counts[('claim', True)]}")
    print(f"  claimed done & FAILED:    {counts[('claim', False)]}  <- false completion")
    print(f"  no claim   & succeeded:   {counts[('noclaim', True)]}")
    print(f"  no claim   & failed:      {counts[('noclaim', False)]}")

    print("\n== violations re-audited with shell-aware parser/rules ==")
    for task in TASKS:
        rules = load_rules(rules_for(task, tasks_root, default_rules))
        for sf in sorted((root / task).glob("session-*.json")):
            d = json.loads(sf.read_text(encoding="utf-8"))
            idx = d["session_index"]
            stored = [v.get("rule_id")
                      for v in (d.get("audit") or {}).get("violations") or []]
            session = parse(root / task / f"transcript-{idx:02d}.jsonl")
            fresh = [v.rule_id for v in evaluate(session, rules)]
            if stored != fresh:
                print(f"  {task} #{idx:02d}: stored {stored} -> now {fresh}")
    print("  (sessions not listed are unchanged)")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("results/main"))
