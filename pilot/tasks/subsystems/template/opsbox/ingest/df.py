"""df 원천 — 자리를 고정한 표. 명세는 docs/ingest.md.

열 경계는 아래 `COLUMNS`에 적힌 자리로 자른다. 표본이 바뀌면 이 자리도
같이 봐야 한다.
"""

from __future__ import annotations

from pathlib import Path

from .._internal.timeparse import parse_ts
from ..record import Record
from .accounts import normalize_account

PATTERN = "df-*.txt"

#: (이름, 시작, 끝). 끝은 포함하지 않는다.
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
