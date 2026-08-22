"""`python -m billsy ...`"""

from __future__ import annotations

import argparse
import json
import sys

from pathlib import Path

from opsbox import config, ingest

from . import dunning, invoice, reconcile, statement


def _records():
    root = Path(__file__).resolve().parent.parent
    settings = config.load(root)
    return ingest.read_all(root / settings["data_dir"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="billsy")
    sub = ap.add_subparsers(dest="cmd", required=True)

    one = sub.add_parser("invoice")
    one.add_argument("--account", required=True)
    one.add_argument("--period", required=True)
    one.add_argument("--json", action="store_true")

    say = sub.add_parser("statement")
    say.add_argument("--account", required=True)
    say.add_argument("--period", required=True)

    due = sub.add_parser("dunning")
    due.add_argument("--as-of", required=True)

    rec = sub.add_parser("reconcile")
    rec.add_argument("--month", required=True)

    args = ap.parse_args(argv)
    records = _records()

    if args.cmd == "invoice":
        built = invoice.build(records, args.account, args.period)
        print(invoice.to_json(built) if args.json else built["total"])
        return 0
    if args.cmd == "statement":
        built = invoice.build(records, args.account, args.period)
        rows = statement.rows(records, args.account, args.period)
        print(statement.render(built, rows), end="")
        return 0
    if args.cmd == "dunning":
        print(json.dumps(dunning.overdue([], args.as_of), indent=2))
        return 0
    if args.cmd == "reconcile":
        print(json.dumps(reconcile.check(records, args.month), indent=2))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
