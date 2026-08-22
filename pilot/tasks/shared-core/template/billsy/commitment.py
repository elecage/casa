"""Committed volume against actual use. The spec is `docs/commitment.md`.

Some accounts signed for a monthly volume. When they use less than that, the
difference is still owed. This reports the gap; it does not bill it yet.
"""

from __future__ import annotations

from core.record import Record

from . import rating

#: The volume an account is assumed to have signed for.
FLOOR = 1000


def committed(account: str) -> int:
    """The monthly volume this account signed for."""
    signed = rating.contracts()
    if account in signed:
        return signed[account].get("committed_units", FLOOR)
    return FLOOR


def used(records: list[Record], account: str, period: str) -> int:
    """How much this account actually used in the period."""
    return sum(r.units for r in records
               if r.account.strip().lower() == account.strip().lower())


def status(records: list[Record], account: str, period: str) -> dict:
    """Committed against actual, and the gap between them."""
    signed = committed(account)
    actual = used(records, account, period)
    short = signed - actual
    rate = rating.rate_for(account) or "0"
    return {
        "account": account,
        "period": period,
        "committed": signed,
        "used": actual,
        "shortfall_units": short,
        "shortfall": str(short * float(rate)),
    }
