"""scs 원천 — 쉼표로 구분된 표. 명세는 docs/readers/scs.md."""

from __future__ import annotations

import csv
from pathlib import Path

from .._internal.timeparse import parse_ts
from ..record import Record

PATTERN = "scs-*.csv"


def read(path: Path) -> list[Record]:
    out = []
    with Path(path).open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            out.append(Record(
                source="scs",
                account=row["account"],
                at=parse_ts(row["at"]),
                units=int(row["units"]),
                status=row.get("status", "ok"),
            ))
    return out
