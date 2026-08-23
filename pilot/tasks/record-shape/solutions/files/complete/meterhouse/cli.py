"""Command line entry point.

    python -m meterhouse <command> [options]

Commands are described in `docs/v03-metering.md`; `--as-of` is described in
`docs/v04-corrections.md`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import alerts, audit, export, rollup
from .corrections import resolve
from .intake import read_dir


def _rules(path: Path) -> list[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))["rules"]
    except (OSError, ValueError, KeyError):
        return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="meterhouse")
    parser.add_argument("command",
                        choices=["intake", "rollup", "alerts", "export",
                                 "audit"])
    parser.add_argument("--data", default="data")
    parser.add_argument("--month", default=None)
    parser.add_argument("--format", default="json", choices=["json", "csv"])
    parser.add_argument("--rules", default="alert-rules.json")
    parser.add_argument("--account", default=None)
    parser.add_argument("--as-of", dest="as_of", default=None)
    args = parser.parse_args(argv)

    readings, skipped = read_dir(Path(args.data))
    _, correction_problems = resolve(readings, args.as_of)
    skipped = sorted(skipped + correction_problems)

    if args.command == "intake":
        print(json.dumps({"readings": [r.as_dict() for r in readings],
                          "skipped": skipped}, indent=2))
        return 0

    if args.month is None:
        parser.error("--month is required for this command")

    if args.command == "audit":
        if args.account is None:
            parser.error("--account is required for audit")
        print(json.dumps(audit.trail(readings, args.month, args.account,
                                     args.as_of), indent=2))
        return 0

    totals = rollup.totals(readings, args.month, args.as_of)

    if args.command == "rollup":
        print(json.dumps({"month": args.month, "as_of": args.as_of,
                          "totals": {a: str(q) for a, q
                                     in sorted(totals.items())}}, indent=2))
    elif args.command == "alerts":
        found = alerts.evaluate(totals, _rules(Path(args.rules)))
        print(json.dumps({"month": args.month, "as_of": args.as_of,
                          "alerts": found}, indent=2))
    elif args.command == "export":
        if args.format == "csv":
            print(export.to_csv(totals, args.month, args.as_of))
        else:
            print(export.to_json(totals, args.month, args.as_of))
    return 0


if __name__ == "__main__":
    sys.exit(main())
