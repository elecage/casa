"""sth 원천 — 탭 구분에 열 이름 줄이 있다. 명세는 docs/readers/sth.md."""

from __future__ import annotations

from pathlib import Path

from .._internal.timeparse import parse_ts
from ..record import Record

PATTERN = "sth-*.tsv"


def read(path: Path) -> list[Record]:
    out = []
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    header = lines[0].split("\t")
    index = {name: i for i, name in enumerate(header)}
    for line in lines[1:]:
        if not line.strip():
            continue
        cell = line.split("\t")
        out.append(Record(
            source="sth",
            account=cell[index["account"]],
            at=parse_ts(cell[index["at"]]),
            units=int(cell[index["qty"]]),
            status=cell[index["status"]] if "status" in index else "ok",
        ))
    return out
