"""무엇을 보관할지 고른다. 명세는 `docs/archive.md`.

**계정 이름을 여기서 다시 맞추고 있다.** 입력 어댑터(서브시스템 A)에
`normalize_account`가 있는데 그것을 안 쓰고 자기 규칙을 따로 둔다. 두 규칙이
어긋나면 한쪽이 못 고른 계정이 조용히 안 걸린 채 남는다.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from ..record import is_billable


def _key(account: str) -> str:
    """보관 목록에서 쓰는 계정 이름."""
    return account.strip().upper()


def older_than(records, as_of: datetime, retain_days: int) -> list:
    """기준일에서 `retain_days`보다 오래된 기록들."""
    cutoff = as_of - timedelta(days=retain_days)
    return [r for r in records if r.at < cutoff]


def by_age(records, as_of: datetime, retain_days: int) -> dict[str, int]:
    """계정별로 보관 대상 기록이 몇 건인가. 나이로 고른 것."""
    out: dict[str, int] = {}
    for record in older_than(records, as_of, retain_days):
        if is_billable(record):
            out[_key(record.account)] = out.get(_key(record.account), 0) + 1
    return dict(sorted(out.items()))


def by_size(records, threshold: int) -> dict[str, int]:
    """계정별 사용량 합계가 문턱을 넘는 것들. 크기로 고른 것."""
    totals: dict[str, int] = {}
    for record in records:
        if is_billable(record):
            totals[_key(record.account)] = (
                totals.get(_key(record.account), 0) + record.units)
    return {name: value for name, value in sorted(totals.items())
            if value > threshold}
