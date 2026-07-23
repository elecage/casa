"""CASA command-line interface.

Usage:
  casa audit <transcript.jsonl> [--rules rules.yaml] [--relevant files.txt]
             [--json] [--out report.md]
  casa report <result-dir> [<result-dir>...] [--tasks-root pilot/tasks]
              [--k-grid 1,3,5,10] [--json] [--out report.md]
"""

from __future__ import annotations

import argparse
import json
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
    p_audit.add_argument("--trajectory", action="store_true",
                         help="Include per-step series and tool sequence (JSON only)")

    p_report = sub.add_parser("report", help="Aggregate a batch of runner results")
    p_report.add_argument("result_dirs", nargs="+",
                          help="Directories with session-NN.json + transcript-NN.jsonl")
    p_report.add_argument("--tasks-root", default="pilot/tasks",
                          help="Root holding <task>/relevant_files.txt for coverage")
    p_report.add_argument("--k-grid", default=None,
                          help="Comma-separated step counts for AUROC@k")
    p_report.add_argument("--json", action="store_true", help="Emit JSON instead of markdown")
    p_report.add_argument("--out", help="Write report to this path instead of stdout")

    args = parser.parse_args(argv)

    if args.command == "audit":
        rules = load_rules(args.rules) if args.rules else None
        relevant = None
        if args.relevant:
            relevant = [
                ln.strip() for ln in Path(args.relevant).read_text(encoding="utf-8").splitlines()
                if ln.strip()
            ]
        result = audit_session(args.transcript, rules=rules, relevant_files=relevant,
                               trajectory=args.trajectory)
        text = to_json(result) if args.json else to_markdown(result)
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(text, encoding="utf-8")
            print(f"report written: {args.out}")
        else:
            print(text)
        return 0

    if args.command == "report":
        from .report import DEFAULT_K_GRID, build_report, report_to_markdown
        k_grid = DEFAULT_K_GRID
        if args.k_grid:
            k_grid = tuple(int(k) for k in args.k_grid.split(","))
        result = build_report(args.result_dirs, tasks_root=args.tasks_root,
                              k_grid=k_grid)
        text = (json.dumps(result, ensure_ascii=False, indent=2) if args.json
                else report_to_markdown(result))
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
