"""Serialization boundary — the only place minor units become a decimal
string and back.

Invariant (holds everywhere): decimal formatting lives here and nowhere
else. Domain code never builds ``"12.34"``-style strings; it hands Money
to this module at the edge.
"""

from __future__ import annotations

from .money import Money


def format_money(amount: Money) -> str:
    """Render Money as ``"<major>.<cc> <CUR>"`` (e.g. ``"12.34 USD"``)."""
    sign = "-" if amount.minor < 0 else ""
    cents = abs(amount.minor)
    return f"{sign}{cents // 100}.{cents % 100:02d} {amount.currency}"


def parse_money(text: str) -> Money:
    """Inverse of :func:`format_money`. Accepts ``"12.34 USD"``."""
    value, _, currency = text.strip().partition(" ")
    neg = value.startswith("-")
    major, _, minor = value.lstrip("-").partition(".")
    minor = (minor + "00")[:2]
    total = int(major) * 100 + int(minor)
    return Money(-total if neg else total, currency or "USD")
