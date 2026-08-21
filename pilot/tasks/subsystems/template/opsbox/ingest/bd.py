"""bd 원천 — 탭으로 구분된 표. 명세는 docs/ingest.md.

이 원천은 수량을 두 벌로 준다. 원래 수량과 청구 수량이 다를 수 있다.
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
