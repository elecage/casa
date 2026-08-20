"""원천별 사용량 절."""

from __future__ import annotations

from ..aggregate import by_source

TITLE = "원천별 사용량"


def render(records: list) -> list[list[str]]:
    return [[source, str(units)] for source, units in by_source(records).items()]
