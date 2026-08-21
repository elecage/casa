"""문턱을 넘었는지 본다. 명세는 `docs/alerts.md`.

**달 경계를 여기서 따로 잡고 있다.** 집계(서브시스템 B)에도 같은 판단이
있는데 둘이 지금 서로 다르다 — B는 `opsbox/report/months.py`의
`MONTH_BASIS`를 보고, 여기는 무조건 표준시로 옮겨 본다. 달 경계에 걸린
기록에서 두 쪽 숫자가 갈린다.
"""

from __future__ import annotations

from .._internal.timeparse import to_utc
from ..record import is_billable


def _month_of(record) -> str:
    """이 기록이 어느 달 것인가.

    구역 표시를 살려 표준시로 옮겨 본다.
    """
    when = to_utc(record.at_raw) if record.at_raw else record.at
    return f"{when.year:04d}-{when.month:02d}"


def monthly_totals(records) -> dict[tuple[str, str], int]:
    """(계정, 달) -> 사용량 합계."""
    out: dict[tuple[str, str], int] = {}
    for record in records:
        if not is_billable(record):
            continue
        key = (record.account, _month_of(record))
        out[key] = out.get(key, 0) + record.units
    return out


def last_seen(records) -> dict[str, int]:
    """계정마다 가장 나중 기록의 사용량."""
    latest: dict[str, tuple] = {}
    for record in records:
        if not is_billable(record):
            continue
        if record.account not in latest or record.at > latest[record.account][0]:
            latest[record.account] = (record.at, record.units)
    return {name: units for name, (_when, units) in latest.items()}


def fire(records, rules) -> list[dict]:
    """문턱을 넘은 규칙마다 알림 하나."""
    totals = monthly_totals(records)
    latest = last_seen(records)
    out = []
    for rule in rules:
        account, limit = rule["account"], rule["limit"]
        basis = rule.get("basis", "month")
        if basis == "month":
            for (name, month), value in sorted(totals.items()):
                if name == account and value > limit:
                    out.append({"account": account, "month": month,
                                "basis": basis, "value": value, "limit": limit})
        elif basis == "last":
            value = latest.get(account)
            if value is not None and value > limit:
                out.append({"account": account, "month": None,
                            "basis": basis, "value": value, "limit": limit})
    return out
