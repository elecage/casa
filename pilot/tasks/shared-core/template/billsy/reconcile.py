"""Billing against operations. The spec is `docs/reconcile.md`.

The two products read the same records. For any month the units operations
reports and the units billing charged for have to be the same number, account
by account. When they are not, one of the two is reading the records
differently and the invoice that went out was wrong.
"""

from __future__ import annotations

from core.record import Record


def check(records: list[Record], month: str) -> dict:
    """Compare the two sides for one month.

    Not written yet. `docs/reconcile.md` says what the result has to carry.
    """
    raise NotImplementedError("see docs/reconcile.md")
