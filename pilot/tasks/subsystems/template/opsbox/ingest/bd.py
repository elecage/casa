"""Source bd — tab separated table. The spec is docs/ingest.md.

This source gives two quantities. The original quantity and the billed
quantity can differ.
"""

from __future__ import annotations

import csv
from pathlib import Path

from .._internal.timeparse import parse_ts
from ..record import Record
from .accounts import normalize_account

PATTERN = "bd-*.tsv"


def read(path: Path) -> list[Record]:
    out = []
    with Path(path).open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            out.append(Record(
                source="bd",
                account=normalize_account(row["account"]),
                at=parse_ts(row["at"]),
                units=int(row["qty"]),
                status=row.get("status", "ok"),
                at_raw=row["at"],
            ))
    return out
