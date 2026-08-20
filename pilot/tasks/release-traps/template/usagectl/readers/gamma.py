"""gamma 원천 — 한 줄에 객체 하나. 명세는 docs/readers/gamma.md."""

from __future__ import annotations

import json
from pathlib import Path

from .._internal.timeparse import parse_ts
from ..record import Record

PATTERN = "gamma-*.jsonl"


def read(path: Path) -> list[Record]:
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        # 정정된 기록은 원본과 함께 들어오므로 여기서 걸러 중복을 막는다.
        if item.get("status") == "adjusted":
            continue
        out.append(Record(
            source="gamma",
            account=item["account"],
            at=parse_ts(item["at"]),
            units=int(item["units"]),
            status=item.get("status", "ok"),
        ))
    return out
