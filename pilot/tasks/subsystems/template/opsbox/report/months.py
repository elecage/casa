"""달 경계를 어디로 잡을 것인가. 명세는 `docs/report.md`의 "달 경계" 절.

**여기가 정해지면 알림 규칙(서브시스템 C)도 같은 기준을 써야 한다.** C는 이
집계 위에 문턱을 거는데, 기준이 다르면 달 경계에 걸린 기록에서 조용히 다른
값이 나온다. 테스트는 초록이고 에러도 안 난다.
"""

from __future__ import annotations

from .._internal.timeparse import to_utc
from ..record import Record

#: 달 경계를 무엇으로 잡나. "local" 또는 "utc".
#: 지금은 원천이 적어 보낸 현지 시각 그대로다. 어느 쪽으로 갈지는
#: `docs/report.md`를 보고 정한다.
MONTH_BASIS = "local"


def moment(record: Record):
    """이 기록을 어느 시각으로 볼 것인가."""
    if MONTH_BASIS == "utc" and record.at_raw:
        return to_utc(record.at_raw)
    return record.at


def month_key(record: Record) -> str:
    """`2026-07` 꼴."""
    when = moment(record)
    return f"{when.year:04d}-{when.month:02d}"
