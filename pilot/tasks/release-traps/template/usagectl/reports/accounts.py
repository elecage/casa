"""계정별 사용량 절."""

from __future__ import annotations

from ..aggregate import by_account

TITLE = "계정별 사용량"


def render(records: list) -> list[list[str]]:
    return [[account, str(units)] for account, units in by_account(records).items()]
