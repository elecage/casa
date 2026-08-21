"""서브시스템들이 주고받는 공통 레코드.

여섯 서브시스템이 각자 자기 파일 형식을 다루지만, 안으로 들어오면 전부
이 모양이 된다. 새 원천을 붙이든 새 리포트를 붙이든 여기를 거친다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Record:
    source: str         # 어느 원천에서 왔나
    account: str        # 사용 주체. 표기는 원천마다 다르다
    at: datetime        # 기록 시각
    units: int          # 청구 대상 수량
    status: str = "ok"  # ok | adjusted | void


def is_billable(record: Record) -> bool:
    """집계에 들어가는 레코드인가.

    ``void``만 뺀다. ``adjusted``는 사후 정정된 것이라 그대로 센다.
    """
    return record.status != "void"
