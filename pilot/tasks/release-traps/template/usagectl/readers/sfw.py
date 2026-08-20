"""sfw 원천 — 고정폭. 열 폭은 docs/readers/sfw.md."""

from __future__ import annotations

from pathlib import Path

from .._internal.timeparse import parse_ts
from ..record import Record

PATTERN = "sfw-*.txt"

_COLUMNS = {"account": (0, 12), "at": (12, 31), "units": (31, 39),
            "status": (39, 47)}


def _slice(line: str, name: str) -> str:
    start, end = _COLUMNS[name]
    return line[start:end].strip()


def read(path: Path) -> list[Record]:
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        out.append(Record(
            source="sfw",
            account=_slice(line, "account"),
            at=parse_ts(_slice(line, "at")),
            units=int(_slice(line, "units")),
            status=_slice(line, "status") or "ok",
        ))
    return out
