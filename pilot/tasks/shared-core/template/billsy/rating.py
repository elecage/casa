"""Usage records -> charge lines. The spec is `docs/rating.md`.

One line per account per month: how many units, at what rate, for how much.
The rate comes from `contracts.json`.
"""

from __future__ import annotations

import json
from pathlib import Path

from core.accounts import normalize_account
from core.money import to_money
from core.months import month_key
from core.record import Record

CONTRACTS = Path(__file__).resolve().parent.parent / "contracts.json"


def contracts() -> dict:
    raw = json.loads(CONTRACTS.read_text(encoding="utf-8"))
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def rate_for(account: str) -> str | None:
    """The rate this account signed, or None if it has no contract."""
    signed = contracts()
    if account in signed:
        return signed[account]["rate_per_unit"]
    wanted = normalize_account(account)
    for name, terms in signed.items():
        if normalize_account(name) == wanted:
            return terms["rate_per_unit"]
    return None


def lines(records: list[Record]) -> list[dict]:
    """Charge lines, one per account per month.

    Sorted so that two runs over the same records produce the same order.
    """
    buckets: dict[tuple[str, str], int] = {}
    for record in records:
        key = (normalize_account(record.account), month_key(record))
        buckets[key] = buckets.get(key, 0) + record.units

    out = []
    for (account, month), units in sorted(buckets.items()):
        rate = rate_for(account)
        if rate is None:
            continue
        out.append({"account": account, "month": month, "units": units,
                    "rate": rate,
                    "amount": str(to_money(rate) * units)})
    return out
