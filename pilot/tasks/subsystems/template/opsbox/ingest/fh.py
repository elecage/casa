"""fh 원천 — 쉼표로 구분된 표인데 열 이름이 다르다. 명세는 docs/ingest.md."""

from __future__ import annotations

import csv
from pathlib import Path

from .._internal.timeparse import parse_ts
from ..record import Record
from .accounts import normalize_account

PATTERN = "fh-*.csv"

#: 이 원천이 쓰는 열 이름 -> 우리가 쓰는 이름.
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
