"""Per-account totals.

Account names are used exactly as the adapter already normalized them
(`opsbox.ingest.accounts.normalize_account`). **They are not normalized again
here** — once the rule lives in two places, one of them quietly leaves an
account sitting on two lines.
"""

from __future__ import annotations

from ..record import is_billable


def by_account(records) -> dict[str, int]:
    out: dict[str, int] = {}
    for record in records:
        if is_billable(record):
            out[record.account] = out.get(record.account, 0) + record.units
    return dict(sorted(out.items()))
