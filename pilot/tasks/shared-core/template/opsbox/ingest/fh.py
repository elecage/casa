"""Source fh — comma separated table with different column names. The spec is
docs/ingest.md."""

from __future__ import annotations

import csv
from pathlib import Path

from .._internal.timeparse import parse_ts
from ..record import Record
from .accounts import normalize_account

PATTERN = "fh-*.csv"

#: The column names this source uses -> the names we use.
HEADERS = {"customer": "account", "when": "at", "amount": "units",
           "flag": "status"}


def read(path: Path) -> list[Record]:
    out = []
    with Path(path).open(encoding="utf-8", newline="") as handle:
        for raw in csv.DictReader(handle):
            row = {HEADERS.get(k, k): v for k, v in raw.items()}
            out.append(Record(
                source="fh",
                account=normalize_account(row["account"]),
                at=parse_ts(row["at"]),
                units=int(row["units"]),
                status=row.get("status", "ok"),
                at_raw=row["at"],
            ))
    return out
