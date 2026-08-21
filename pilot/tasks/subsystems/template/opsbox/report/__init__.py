"""서브시스템 B — 집계와 리포트. 명세는 `docs/report.md`.

입력 어댑터(서브시스템 A)가 내놓은 레코드를 받아 달별·원천별·계정별로
묶고 텍스트 리포트를 낸다.

**여기서 정해지는 것 둘이 다른 서브시스템으로 넘어간다.**

- **달 경계**(`months.MONTH_BASIS`) — 알림 규칙(C)이 같은 기준을 써야 한다.
- **날짜 표기**(`dates.DATE_STYLE`) — 보관과 정리(D)의 목록도 같은 표기여야 한다.
"""

from __future__ import annotations

from . import accounts, dates, months, render, sources, totals
from .accounts import by_account
from .dates import format_date
from .months import month_key
from .render import render_text
from .sources import by_source
from .totals import record_count, total_units


def build(records) -> dict:
    """리포트에 들어갈 것을 한 덩어리로 모은다."""
    per_month: dict[str, list] = {}
    for record in records:
        per_month.setdefault(month_key(record), []).append(record)
    return {
        "total_units": total_units(records),
        "record_count": record_count(records),
        "by_source": by_source(records),
        "by_account": by_account(records),
        "by_month": {key: total_units(rows)
                     for key, rows in sorted(per_month.items())},
    }
