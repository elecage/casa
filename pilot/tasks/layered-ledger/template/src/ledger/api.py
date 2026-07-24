"""Public entry points — wires validation, domain, and serialization for
callers. Thin by design: it delegates to the domain layer and never does
money arithmetic itself.
"""

from __future__ import annotations

from .domain import SplitResult, split_with_fee, transfer
from .money import Money
from .serialize import format_money


def process_split(total: Money, n: int, rate_bps: int) -> SplitResult:
    """Entry point for a fee-bearing split (delegates to the domain)."""
    return split_with_fee(total, n, rate_bps)


def process_transfer(balance: Money, amount: Money) -> Money:
    return transfer(balance, amount)


def render_split(result: SplitResult) -> list[str]:
    """Format a split result for display, at the serialization boundary."""
    return [format_money(m) for m in result.net]
