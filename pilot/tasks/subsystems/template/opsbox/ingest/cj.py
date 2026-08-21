"""cj 원천 — 한 줄에 JSON 하나. 명세는 docs/ingest.md."""

from __future__ import annotations

import json
from pathlib import Path

from .._internal.timeparse import parse_ts
from ..record import Record
from .accounts import normalize_account

PATTERN = "cj-*.jsonl"


def read(path: Path) -> list[Record]:
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        out.append(Record(
            source="cj",
            account=normalize_account(row["acct"]),
            at=parse_ts(row["ts"]),
            units=int(row["units"]),
            status=row.get("state", "ok"),
        ))
    return out
