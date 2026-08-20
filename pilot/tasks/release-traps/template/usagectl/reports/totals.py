"""합계 절."""

from __future__ import annotations

from ..aggregate import grand_total

TITLE = "합계"


def render(records: list) -> list[list[str]]:
    return [["total", str(grand_total(records))]]
