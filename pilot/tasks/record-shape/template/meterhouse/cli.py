"""Command line entry point.

    python -m meterhouse <command> [options]

Commands are described in `docs/v03-metering.md`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import alerts, export, rollup
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

    if args.command == "intake":
        print(json.dumps({"readings": [r.as_dict() for r in readings],
                          "skipped": skipped}, indent=2))
        return 0

    if args.month is None:
        parser.error("--month is required for this command")
    totals = rollup.totals(readings, args.month)

    if args.command == "rollup":
        print(json.dumps({"month": args.month,
                          "totals": {a: str(q) for a, q
                                     in sorted(totals.items())}}, indent=2))
    elif args.command == "alerts":
        found = alerts.evaluate(totals, _rules(Path(args.rules)))
        print(json.dumps({"month": args.month, "alerts": found}, indent=2))
    elif args.command == "export":
        if args.format == "csv":
            print(export.to_csv(totals, args.month))
        else:
            print(export.to_json(totals, args.month))
    elif args.command == "audit":
        raise SystemExit("audit is planned for v0.5 (docs/v05-audit.md)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
