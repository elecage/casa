"""Threshold alerts.

Rules live in `alert-rules.json`. See `docs/v03-metering.md` for the shape.
"""

from __future__ import annotations

from decimal import Decimal


def evaluate(totals: dict[str, Decimal], rules: list[dict]) -> list[dict]:
    """Return one alert per account that trips a rule."""
    raise NotImplementedError("alerts are not wired up yet")
