"""sjs 원천 — 한 줄에 객체 하나. 명세는 docs/readers/sjs.md."""

from __future__ import annotations

import json
from pathlib import Path

from .._internal.timeparse import parse_ts
from ..record import Record

PATTERN = "sjs-*.jsonl"


def read(path: Path) -> list[Record]:
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        out.append(Record(
            source="sjs",
            account=item["account"],
            at=parse_ts(item["at"]),
            units=int(item["units"]),
            status=item.get("state", "ok"),
        ))
    return out
