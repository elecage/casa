"""Which invoices are overdue. The spec is `docs/dunning.md`.

An invoice is overdue when the terms days have passed since it was issued.
The terms come from `contracts.json`.
"""

from __future__ import annotations

import datetime

from . import rating


def due_on(issued_on: str, account: str) -> str:
    """When this invoice falls due."""
    signed = rating.contracts()
    terms = signed.get(account, {}).get("terms_days", 30)
    issued = datetime.date.fromisoformat(issued_on)
    return (issued + datetime.timedelta(days=terms)).isoformat()


def overdue(invoices: list[dict], as_of: str) -> list[dict]:
    """The invoices that are past due at `as_of`.

    Paid invoices carry `"paid_on"`; those are never overdue.
    """
    today = datetime.date.fromisoformat(as_of)
    out = []
    for invoice in invoices:
        if invoice.get("paid_on"):
            continue
        due = due_on(invoice["issued_on"], invoice["account"])
        if datetime.date.fromisoformat(due) <= today:
            out.append({"account": invoice["account"],
                        "period": invoice["period"],
                        "due_on": due, "total": invoice["total"]})
    return out
