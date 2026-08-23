"""Charge lines -> one invoice. The spec is `docs/invoice.md`.

An invoice covers one account for one period and carries the lines, the
subtotal, the credits that came off, and the total.
"""

from __future__ import annotations

import datetime
import json

from core.money import round_money, sum_money, to_money
from core.record import Record
from core.timeparse import parse_ts

from . import credits as credits_mod
from . import rating


def _period_of(record: Record) -> str:
    """Which billing period this record falls in."""
    when = parse_ts(record.at_raw) if record.at_raw else record.at
    return f"{when.year:04d}-{when.month:02d}"


def build(records: list[Record], account: str, period: str) -> dict:
    """The invoice for one account and one period."""
    mine = [r for r in records
            if r.account.strip().lower() == account.strip().lower()
            and _period_of(r) == period]
    charge_lines = [line for line in rating.lines(mine)
                    if line["month"] == period]
    subtotal = sum_money(line["amount"] for line in charge_lines)
    applied = credits_mod.for_account(account, period)
    total = round_money(subtotal - sum_money(c["amount"] for c in applied))
    return {
        "account": account,
        "period": period,
        "lines": charge_lines,
        "subtotal": str(subtotal),
        "credits": applied,
        "total": str(total),
        "issued_on": datetime.date.today().isoformat(),
    }


def to_json(invoice: dict) -> str:
    return json.dumps(invoice, indent=2, sort_keys=True)
