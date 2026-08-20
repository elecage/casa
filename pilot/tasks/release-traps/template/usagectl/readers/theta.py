"""theta 원천 — 탭 구분. 명세는 docs/readers/theta.md.

원천 쪽 수집기가 이따금 줄을 자른 채 보낸다. 자른 자리가 여러 바이트짜리
글자 가운데면 그 줄은 글자로 읽히지 않는다.
"""

from __future__ import annotations

from pathlib import Path

from .._internal.timeparse import parse_ts
from ..record import Record

PATTERN = "theta-*.tsv"


def read(path: Path) -> list[Record]:
    out = []
    text = Path(path).read_bytes().decode("utf-8")
    for line in text.splitlines():
        if not line.strip():
            continue
        account, at, units, status = line.split("\t")
        out.append(Record(
            source="theta",
            account=account,
            at=parse_ts(at),
            units=int(units),
            status=status or "ok",
        ))
    return out
