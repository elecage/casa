"""Command line entry point.

    python -m opsbox report
    python -m opsbox alerts
    python -m opsbox archive
    python -m opsbox export --out out.csv
    python -m opsbox backfill --month 2026-07
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from . import alerts, archive, backfill, config, export, ingest, report


def _load(root: Path):
    settings = config.load(root)
    records = ingest.read_all(root / settings["data_dir"])
    return settings, records


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="opsbox")
    parser.add_argument("command",
                        choices=["report", "alerts", "archive", "export",
                                 "backfill"])
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--month", default="2026-07")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    settings, records = _load(args.root)
    built = report.build(records)

    if args.command == "report":
        if args.json:
            print(json.dumps(built, ensure_ascii=False, indent=2))
        else:
            print(report.render_text(built), end="")
    elif args.command == "alerts":
        fired = alerts.fire(records, alerts.load(args.root))
        # Also report which months were counted. Looking only at what fired
        # hides the disagreement whenever nothing fires in a month where the
        # alerts and the report already disagree.
        months = sorted({month for _account, month
                         in alerts.monthly_totals(records)})
        print(json.dumps({"months": months, "fired": fired},
                         ensure_ascii=False, indent=2))
    elif args.command == "archive":
        as_of = datetime.fromisoformat(settings["as_of"])
        picked = archive.by_age(records, as_of, settings["retain_days"])
        print(json.dumps(archive.render(picked, as_of), ensure_ascii=False,
                         indent=2))
    elif args.command == "export":
        text = export.to_csv(built)
        if args.out:
            Path(args.out).write_text(text, encoding="utf-8")
        else:
            print(text, end="")
    elif args.command == "backfill":
        out = backfill.delta(args.root, records, args.month)
        print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
