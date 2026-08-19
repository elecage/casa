#!/usr/bin/env python3
"""casefile — 점검 기록 정규화 도구.

지금은 CSV 읽기만 절반 되어 있다.
"""

import argparse
import csv
import json
from pathlib import Path

REQUIRED = ("case_id", "site", "inspected_at", "inspector", "status")


def read_csv(path):
    rows = []
    with open(path, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            rows.append(row)
    return rows


def build(args):
    records = []
    if args.csv:
        records.extend(read_csv(args.csv))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(records, ensure_ascii=False, indent=2),
                   encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--csv")
    b.add_argument("--fixed")
    b.add_argument("--out", required=True)
    b.set_defaults(func=build)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
