"""ssc 원천 — 세미콜론 구분. 명세는 docs/readers/ssc.md."""

from __future__ import annotations

from pathlib import Path

from .._internal.timeparse import parse_ts
from ..record import Record

PATTERN = "ssc-*.txt"


def read(path: Path) -> list[Record]:
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        account, at, units, status = (part.strip() for part in line.split(";"))
        out.append(Record(
            source="ssc",
            account=account,
            at=parse_ts(at),
            units=int(units),
            status=status or "ok",
        ))
    return out
