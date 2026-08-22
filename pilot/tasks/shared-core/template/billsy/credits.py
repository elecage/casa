"""Agreed credits come off an invoice. The spec is `docs/credits.md`.

Credits are agreed with the customer out of band and written into
`credits.json` by hand. Billing only applies them.
"""

from __future__ import annotations

import json
from pathlib import Path

CREDITS = Path(__file__).resolve().parent.parent / "credits.json"


def all_credits() -> dict:
    raw = json.loads(CREDITS.read_text(encoding="utf-8"))
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def for_account(account: str, period: str) -> list[dict]:
    """The credits that come off this account's invoice for this period."""
    out = []
    for entry in all_credits().get(period, []):
        if entry["account"] == account:
            out.append({"amount": entry["amount"], "reason": entry["reason"]})
    return out
