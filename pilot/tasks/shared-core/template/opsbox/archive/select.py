"""Picks what gets archived. The spec is `docs/archive.md`.

**Account names are normalized again here.** The input adapters (subsystem A)
have `normalize_account`, and this does not use it but keeps a rule of its
own. When the two rules disagree, the accounts one of them failed to pick
quietly stay behind.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from ..record import is_billable


def _key(account: str) -> str:
    """The account name used in the archive manifest."""
    return account.strip().upper()


def older_than(records, as_of: datetime, retain_days: int) -> list:
    """The records older than `retain_days` counting back from the reference
    date."""
    cutoff = as_of - timedelta(days=retain_days)
    return [r for r in records if r.at < cutoff]


def by_age(records, as_of: datetime, retain_days: int) -> dict[str, int]:
    """How many records per account are up for archiving. Picked by age."""
    out: dict[str, int] = {}
    for record in older_than(records, as_of, retain_days):
        if is_billable(record):
            out[_key(record.account)] = out.get(_key(record.account), 0) + 1
    return dict(sorted(out.items()))


def by_size(records, threshold: int) -> dict[str, int]:
    """The accounts whose units total is over the threshold. Picked by size."""
    totals: dict[str, int] = {}
    for record in records:
        if is_billable(record):
            totals[_key(record.account)] = (
                totals.get(_key(record.account), 0) + record.units)
    return {name: value for name, value in sorted(totals.items())
            if value > threshold}
