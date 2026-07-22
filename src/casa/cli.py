"""CASA command-line interface.

Usage:
  casa audit <transcript.jsonl> [--rules rules.yaml] [--relevant files.txt]
             [--json] [--out report.md]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .audit import audit_session, to_json, to_markdown
from .rules import load_rules


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="casa", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_audit = sub.add_parser("audit", help="Score one session transcript")
    p_audit.add_argument("transcript", help="Path to Claude Code session .jsonl")
    p_audit.add_argument("--rules", help="Rules YAML (see rules/)")
    p_audit.add_argument("--relevant",
                         help="Text file with one relevant file path per line (for coverage)")
    p_audit.add_argument("--json", action="store_true", help="Emit JSON instead of markdown")
    p_audit.add_argument("--out", help="Write report to this path instead of stdout")

    args = parser.parse_args(argv)

    if args.command == "audit":
        rules = load_rules(args.rules) if args.rules else None
        relevant = None
        if args.relevant:
            relevant = [
                ln.strip() for ln in Path(args.relevant).read_text(encoding="utf-8").splitlines()
                if ln.strip()
            ]
        result = audit_session(args.transcript, rules=rules, relevant_files=relevant)
        text = to_json(result) if args.json else to_markdown(result)
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(text, encoding="utf-8")
            print(f"report written: {args.out}")
        else:
            print(text)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
