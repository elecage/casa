"""날짜별 사용량 절."""

from __future__ import annotations

from ..aggregate import by_day

TITLE = "날짜별 사용량"


def render(records: list) -> list[list[str]]:
    return [[day, str(units)] for day, units in by_day(records).items()]
