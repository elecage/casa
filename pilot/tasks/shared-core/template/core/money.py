"""How money is rounded. The spec sections are "Rounding" in
`docs/report.md` and in `docs/invoice.md`.

**Both products put money through here.** Operations rounds so that a report
column adds up on screen; billing rounds so that an invoice total matches what
the contract says is owed. Those are not the same rule, and the difference
only shows up in the last unit of currency.

Right now nothing is settled: `ROUNDING` is the rule that happened to be here
first.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

#: "per_line" rounds each line and adds the rounded lines.
#: "total_only" adds the unrounded lines and rounds once at the end.
ROUNDING = "per_line"

CENT = Decimal("0.01")


def to_money(value) -> Decimal:
    """A currency amount, not yet rounded."""
    return Decimal(str(value))


def round_money(value) -> Decimal:
    return to_money(value).quantize(CENT, rounding=ROUND_HALF_UP)


def sum_money(values) -> Decimal:
    """Add up amounts under the settled rounding rule.

    With "per_line" each amount is rounded before it is added. With
    "total_only" the amounts are added as they are and the sum is rounded.
    The two differ by a cent or two on a long invoice, and nothing raises.
    """
    amounts = [to_money(v) for v in values]
    if ROUNDING == "per_line":
        return sum((round_money(a) for a in amounts), Decimal("0"))
    return round_money(sum(amounts, Decimal("0")))
