"""What the customer reads. The spec is `docs/statement.md`.

A statement is the invoice plus the usage behind it, in a form a person can
check against their own records.
"""

from __future__ import annotations

from core.accounts import normalize_account
from core.months import month_key
from core.record import Record


def rows(records: list[Record], account: str, period: str) -> list[dict]:
    """The usage rows behind one invoice, newest last."""
    mine = [r for r in records
            if normalize_account(r.account) == normalize_account(account)
            and month_key(r) == period
            and r.status != "void"]
    mine.sort(key=lambda r: (r.at, r.source))
    return [{"at": r.at.isoformat(), "source": r.source,
             "units": r.units, "status": r.status} for r in mine]


def render(invoice: dict, usage: list[dict]) -> str:
    """The statement as text."""
    out = [f"Statement for {invoice['account']} — {invoice['period']}", ""]
    out.append(f"{'when':<20}{'source':<8}{'units':>7}  status")
    for row in usage:
        out.append(f"{row['at']:<20}{row['source']:<8}{row['units']:>7}  "
                   f"{row['status']}")
    out.append("")
    out.append(f"subtotal {invoice['subtotal']}")
    for credit in invoice["credits"]:
        out.append(f"credit   -{credit['amount']}  ({credit['reason']})")
    out.append(f"total    {invoice['total']}")
    return "\n".join(out) + "\n"
