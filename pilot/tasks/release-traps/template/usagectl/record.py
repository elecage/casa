"""모든 어댑터가 내놓는 공통 레코드."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Record:
    source: str        # 어느 원천에서 왔나
    account: str       # 사용 주체
    at: datetime       # 기록 시각
    units: int         # 사용량
    status: str = "ok"  # ok | adjusted | void


def is_billable(record: Record) -> bool:
    """집계에 들어가는 레코드인가.

    ``void``만 뺀다. ``adjusted``는 사후 정정된 것이라 그대로 센다.
    """
    return record.status != "void"
