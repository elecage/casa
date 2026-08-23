"""What the customer has already paid. The spec is `docs/payments.md`.

A payment settles one billing period. It names the period it settles; the day
it arrives is a separate thing and is often in the following month.

The bank writes an account name the way it appears on the transfer. That is a
third spelling, on top of the one the sources use and the one the contract
uses.
"""

from __future__ import annotations

import json
from pathlib import Path

PAYMENTS = Path(__file__).resolve().parent.parent / "payments.json"


def all_payments() -> dict:
    raw = json.loads(PAYMENTS.read_text(encoding="utf-8"))
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def for_account(account: str, period: str) -> list[dict]:
    """The payments that settle this account's invoice for this period."""
    out = []
    for group, entries in all_payments().items():
        for entry in entries:
            if entry["received_on"][:7] != period:
                continue
            if entry["account"].strip().lower() != account.strip().lower():
                continue
            out.append({"amount": entry["amount"],
                        "received_on": entry["received_on"],
                        "ref": entry["ref"]})
    return out


def settle(invoice: dict) -> dict:
    """What is still owed on one invoice once the payments are taken off."""
    paid = for_account(invoice["account"], invoice["period"])
    taken = sum(float(entry["amount"]) for entry in paid)
    balance = float(invoice["total"]) - taken
    return {
        "account": invoice["account"],
        "period": invoice["period"],
        "invoiced": invoice["total"],
        "paid": str(taken),
        "balance": str(balance),
        "payments": paid,
    }
