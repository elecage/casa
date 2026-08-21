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
    at: datetime        # 기록 시각. `parse_ts` 로 읽은 현지 시각이다
    units: int          # 청구 대상 수량
    status: str = "ok"  # ok | adjusted | void
    at_raw: str = ""    # 원천이 적어 보낸 시각 문자열 그대로

    # `at_raw` 를 들고 다니는 이유: `parse_ts` 는 구역 표시를 떼고 읽으므로
    # `at` 만으로는 그 기록이 어느 구역에서 왔는지 되살릴 수 없다. 달 경계를
    # 표준시로 잡을지 현지 시각으로 잡을지는 집계 쪽(서브시스템 B)이 정하는데,
    # 원문이 없으면 그 선택지가 아예 없어진다.


def is_billable(record: Record) -> bool:
    """집계에 들어가는 레코드인가.

    ``void``만 뺀다. ``adjusted``는 사후 정정된 것이라 그대로 센다.
    """
    return record.status != "void"
