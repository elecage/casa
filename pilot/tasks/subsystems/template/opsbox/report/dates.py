"""리포트가 날짜를 적는 방식. 명세는 `docs/report.md`의 "날짜 표기" 절.

**보관과 정리(서브시스템 D)도 목록에 날짜를 적는다.** 두 문서가 표기를
서로 다르게 말하고 있어서 한 저장소에서 둘 다 만족시킬 수 없다. 어느 쪽으로
통일했는지가 산출물에 남는다.
"""

from __future__ import annotations

from datetime import datetime

#: "dash" 는 `2026-07-03`, "slash" 는 `2026/07/03`.
DATE_STYLE = "dash"


def format_date(when: datetime) -> str:
    if DATE_STYLE == "slash":
        return f"{when.year:04d}/{when.month:02d}/{when.day:02d}"
    return f"{when.year:04d}-{when.month:02d}-{when.day:02d}"
