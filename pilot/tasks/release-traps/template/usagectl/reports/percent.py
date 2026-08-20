"""계정별 점유율 절.

점유율은 소수점 첫째 자리까지 낸다. 반올림 방식은 docs/spec.md에 적혀 있다.
"""

from __future__ import annotations

from ..aggregate import by_account, grand_total

TITLE = "계정별 점유율"


def _round_half_up(value: float, digits: int = 1) -> float:
    factor = 10 ** digits
    scaled = value * factor
    return int(scaled + 0.5) / factor


def render(records: list) -> list[list[str]]:
    total = grand_total(records)
    if not total:
        return []
    rows = []
    for account, units in by_account(records).items():
        share = _round_half_up(units * 100 / total)
        rows.append([account, f"{share:.1f}"])
    return rows
