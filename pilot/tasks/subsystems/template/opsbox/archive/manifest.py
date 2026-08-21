"""보관 목록을 적는다. 모양은 `docs/archive.md`."""

from __future__ import annotations

from datetime import datetime

from ..report.dates import format_date


def render(picked: dict[str, int], as_of: datetime) -> dict:
    """보관 목록 한 벌.

    날짜는 `opsbox.report.dates.format_date`로 적는다 — 저장소에 표기가
    두 벌 생기지 않게 한 자리에서만 만든다.
    """
    return {
        "as_of": format_date(as_of),
        "accounts": [{"account": name, "records": count}
                     for name, count in sorted(picked.items())],
    }
