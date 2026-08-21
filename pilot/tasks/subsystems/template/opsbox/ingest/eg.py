"""eg 원천 — 한 줄에 `key=value` 쌍들. 명세는 docs/ingest.md."""

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
        out.append(Record(
            source="eg",
            account=normalize_account(row["account"]),
            at=parse_ts(row["at"]),
            units=int(row["units"]),
            status=row.get("status", "ok"),
        ))
    return out
