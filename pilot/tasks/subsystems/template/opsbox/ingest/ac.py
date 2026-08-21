"""ac 원천 — 쉼표로 구분된 표. 명세는 docs/ingest.md."""

from __future__ import annotations

import csv
from pathlib import Path

from .._internal.timeparse import parse_ts
from ..record import Record
from .accounts import normalize_account

PATTERN = "ac-*.csv"


def read(path: Path) -> list[Record]:
    out = []
    with Path(path).open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            out.append(Record(
                source="ac",
                account=normalize_account(row["account"]),
                at=parse_ts(row["at"]),
                units=int(row["units"]),
                status=row.get("status", "ok"),
            ))
    return out
