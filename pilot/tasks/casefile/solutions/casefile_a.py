#!/usr/bin/env python3
"""Reference implementation for the casefile task.

Three variants are generated from this one file by swapping the CONVENTIONS
block (see make_solutions.py):

    A       timestamps in UTC, source-prefixed ids, missing note as ""
    B       timestamps keep an explicit offset, plain ids, missing note as null
    mixed   the same three choices applied inconsistently across code paths

A and B must both score full marks. That is the check that the task grades
consistency rather than which side was picked — if only one of them passes,
the grader is secretly demanding an answer and the design is broken.
"""

import argparse
import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

# --- CONVENTIONS ----------------------------------------------------------
TIME_UTC = True
ID_PREFIXED = True
MISSING_NOTE = ""
ID_FIELD = "record_id"
ID_PREFIXED_FIXED = True
# --- end CONVENTIONS --------------------------------------------------------------------------------------------------------

REQUIRED = ("id", "site", "inspected_at", "inspector", "status")
FIXED_COLUMNS = {
    "id": (0, 6), "site": (7, 14), "inspected_at": (15, 31),
    "inspector": (32, 40), "status": (41, 46), "note": (47, None),
}
CONFLICT_FIELDS = ("inspector", "status", "note")


def parse_instant(text):
    """A timezone-aware datetime, or None when the text is unusable."""
    text = (text or "").strip()
    if not text:
        return None
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError:
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


def render_time(instant, utc=None):
    use_utc = TIME_UTC if utc is None else utc
    if use_utc:
        return instant.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if instant.utcoffset() == timedelta(0):
        instant = instant.replace(tzinfo=timezone(timedelta(0)))
    return instant.isoformat()


def render_id(raw, source, prefixed=None):
    use_prefix = ID_PREFIXED if prefixed is None else prefixed
    return f"{source}:{raw}" if use_prefix else raw


def natural_key(record):
    """The identifier without a source prefix — stable across conventions."""
    return str(record.get(ID_FIELD, "")).rsplit(":", 1)[-1]


def read_csv(path):
    rows = []
    with open(path, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            rows.append({
                "id": (row.get("record_id") or row.get("case_id") or "").strip(),
                "site": (row.get("site") or "").strip(),
                "inspected_at": (row.get("inspected_at") or "").strip(),
                "inspector": (row.get("inspector") or "").strip(),
                "status": (row.get("status") or "").strip(),
                "note": (row.get("note") or "").strip(),
            })
    return rows


def read_fixed(path):
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = {}
        for field, (start, end) in FIXED_COLUMNS.items():
            chunk = line[start:end] if end is not None else line[start:]
            row[field] = chunk.strip()
        rows.append(row)
    return rows


def normalise(row, source, prefixed=None):
    """A finished record, or (None, reason) when the row must be quarantined."""
    missing = [f for f in REQUIRED if not row.get(f)]
    if missing:
        return None, "missing:" + ",".join(missing)
    instant = parse_instant(row["inspected_at"])
    if instant is None:
        return None, "unparsable_time"
    note = row.get("note") or ""
    record = {
        ID_FIELD: render_id(row["id"], source, prefixed),
        "site": row["site"],
        "inspected_at": render_time(instant),
        "inspector": row["inspector"],
        "status": row["status"],
        "note": note if note else MISSING_NOTE,
        "sources": [source],
    }
    return record, instant


def within_range(instant, since, until):
    start, end = parse_instant(since), parse_instant(until)
    if start and instant < start:
        return False
    if end and instant > end:
        return False
    return True


def build(args):
    records, quarantine, audit, conflicts = [], [], [], []
    merge_index = {}

    out = Path(args.out)
    if getattr(args, "append", False) and out.exists():
        # Incremental update: whatever is already in the case file stays.
        try:
            for record in json.loads(out.read_text(encoding="utf-8")):
                # Key on the instant, never on the rendered string: variant B
                # writes +09:00 where A writes Z, and the same inspection must
                # merge under both.
                stamp = parse_instant(record.get("inspected_at"))
                key = (natural_key(record), record.get("site"),
                       stamp.astimezone(timezone.utc) if stamp else None)
                merge_index[key] = record
                records.append(record)
        except (OSError, ValueError):
            pass

    def ingest(rows, source, prefixed=None):
        kept = 0
        for row in rows:
            record, extra = normalise(row, source, prefixed)
            if record is None:
                quarantine.append({
                    ID_FIELD: row.get("id", ""), "site": row.get("site", ""),
                    "source": source, "reason": extra,
                })
                continue
            if not within_range(extra, getattr(args, "since", None),
                                getattr(args, "until", None)):
                continue
            key = (row["id"], row["site"], extra.astimezone(timezone.utc))
            if key in merge_index:
                merged = merge_index[key]
                for field in CONFLICT_FIELDS:
                    if merged.get(field) != record.get(field):
                        conflicts.append({
                            ID_FIELD: merged.get(ID_FIELD), "site": record["site"],
                            "field": field, "kept": merged.get(field),
                            "seen": record.get(field), "source": source,
                        })
                if source not in merged["sources"]:
                    merged["sources"].append(source)
            else:
                merge_index[key] = record
                records.append(record)
            kept += 1
        audit.append(f"{source} rows={len(rows)} kept={kept}")

    if args.csv:
        ingest(read_csv(args.csv), Path(args.csv).name)
    if args.fixed:
        ingest(read_fixed(args.fixed), Path(args.fixed).name,
               prefixed=ID_PREFIXED_FIXED)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(records, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    (out.parent / "quarantine.json").write_text(
        json.dumps(quarantine, ensure_ascii=False, indent=2), encoding="utf-8")
    (out.parent / "conflicts.json").write_text(
        json.dumps(conflicts, ensure_ascii=False, indent=2), encoding="utf-8")
    (out.parent / "audit.log").write_text(
        "\n".join(audit) + f"\nrecords={len(records)}\n", encoding="utf-8")

    split = getattr(args, "split_by_site", None)
    if split:
        target = Path(split)
        target.mkdir(parents=True, exist_ok=True)
        by_site = {}
        for record in records:
            by_site.setdefault(record["site"], []).append(record)
        for site, rows in by_site.items():
            (target / f"{site}.json").write_text(
                json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def report(args):
    records = json.loads(Path(args.inp).read_text(encoding="utf-8"))
    by_status, by_site = {}, {}
    for record in records:
        by_status[record["status"]] = by_status.get(record["status"], 0) + 1
        by_site[record["site"]] = by_site.get(record["site"], 0) + 1
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(
        {"total": len(records), "by_status": by_status, "by_site": by_site},
        ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--csv")
    b.add_argument("--fixed")
    b.add_argument("--out", required=True)
    b.add_argument("--append", action="store_true")
    b.add_argument("--since")
    b.add_argument("--until")
    b.add_argument("--split-by-site", dest="split_by_site")
    b.set_defaults(func=build)
    r = sub.add_parser("report")
    r.add_argument("--in", dest="inp", required=True)
    r.add_argument("--out", required=True)
    r.set_defaults(func=report)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
