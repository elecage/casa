"""Source eg — `key=value` pairs, several per line. The spec is
docs/ingest.md.

Not every line carries every key. Lines are skipped when the status is not
there, so a half-written line does not land in the totals as something it is
not.
"""

from __future__ import annotations

from pathlib import Path

from .._internal.timeparse import parse_ts
from ..record import Record
from .accounts import normalize_account

PATTERN = "eg-*.txt"


def _pairs(line: str) -> dict:
    out = {}
    for chunk in line.split():
        if "=" in chunk:
            key, value = chunk.split("=", 1)
            out[key] = value
    return out


def read(path: Path) -> list[Record]:
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = _pairs(line)
        if not row.get("status"):
            continue
        out.append(Record(
            source="eg",
            account=normalize_account(row["account"]),
            at=parse_ts(row["at"]),
            units=int(row["units"]),
            status=row.get("status", "ok"),
                at_raw=row["at"],
        ))
    return out
