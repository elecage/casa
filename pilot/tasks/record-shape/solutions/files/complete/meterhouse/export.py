"""Export monthly totals for the billing team."""

from __future__ import annotations

import io
import json
from decimal import Decimal


def to_json(totals: dict[str, Decimal], month: str,
            as_of: str | None = None) -> str:
    rows = [{"account": account, "quantity": str(quantity)}
            for account, quantity in sorted(totals.items())]
    return json.dumps({"month": month, "as_of": as_of, "rows": rows}, indent=2)


def to_csv(totals: dict[str, Decimal], month: str,
           as_of: str | None = None) -> str:
    out = io.StringIO()
    out.write("account,quantity\n")
    for account, quantity in sorted(totals.items()):
        out.write(f"{account},{quantity}\n")
    return out.getvalue().rstrip("\n")
