"""Source df — fixed-width table. The spec is docs/ingest.md.

Column boundaries are cut at the positions listed in `COLUMNS` below. If the
sample changes, these positions have to be checked along with it.
"""

from __future__ import annotations

from pathlib import Path

from .._internal.timeparse import parse_ts
from ..record import Record
from .accounts import normalize_account

PATTERN = "df-*.txt"

#: (name, start, end). The end position is not included.
COLUMNS = (
    ("account", 0, 10),
    ("at", 10, 29),
    ("units", 29, 34),
    ("status", 36, 44),
)


def _cut(line: str) -> dict:
    return {name: line[start:end].strip() for name, start, end in COLUMNS}


def read(path: Path) -> list[Record]:
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = _cut(line)
        out.append(Record(
            source="df",
            account=normalize_account(row["account"]),
            at=parse_ts(row["at"]),
            units=int(row["units"]),
            status=row["status"] or "ok",
                at_raw=row["at"],
        ))
    return out
