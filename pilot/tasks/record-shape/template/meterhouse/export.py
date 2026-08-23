"""Export monthly totals for the billing team."""

from __future__ import annotations

import json
from decimal import Decimal


def to_json(totals: dict[str, Decimal], month: str) -> str:
    rows = [{"account": account, "quantity": str(quantity)}
            for account, quantity in sorted(totals.items())]
    return json.dumps({"month": month, "rows": rows}, indent=2)


def to_csv(totals: dict[str, Decimal], month: str) -> str:
    raise NotImplementedError("csv export is not wired up yet")
