"""월별 사용량 절."""

from __future__ import annotations

from ..aggregate import by_month

TITLE = "월별 사용량"


def render(records: list) -> list[list[str]]:
    return [[month, str(units)] for month, units in by_month(records).items()]
