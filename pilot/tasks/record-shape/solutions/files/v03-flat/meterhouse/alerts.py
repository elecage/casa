"""Threshold alerts.

Rules live in `alert-rules.json`. See `docs/v03-metering.md` for the shape.
"""

from __future__ import annotations

from decimal import Decimal


def evaluate(totals: dict[str, Decimal], rules: list[dict]) -> list[dict]:
    """Return one alert per account that trips a rule."""
    found = []
    for account, quantity in totals.items():
        for rule in rules:
            try:
                over = Decimal(str(rule.get("over")))
            except (TypeError, ValueError):
                continue
            if quantity > over:
                found.append({"account": account,
                              "rule": rule.get("name"),
                              "severity": rule.get("severity"),
                              "quantity": str(quantity)})
    return sorted(found, key=lambda a: (a["account"], a["rule"] or ""))
