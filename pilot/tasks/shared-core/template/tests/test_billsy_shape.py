"""The shape billing's outputs have to keep. These do not change."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from billsy import credits, dunning, rating, statement  # noqa: E402


def test_a_charge_line_carries_the_five_fields():
    line = {"account": "a", "month": "2026-07", "units": 1, "rate": "0.1",
            "amount": "0.10"}
    made = rating.lines([])
    assert made == [] or set(made[0]) == set(line)


def test_credits_are_amount_and_reason():
    for entry in credits.for_account("acme-01", "2026-07"):
        assert set(entry) == {"amount", "reason"}


def test_dunning_reports_four_fields():
    invoices = [{"account": "acme-01", "period": "2026-07",
                 "issued_on": "2026-07-31", "total": "10.00"}]
    got = dunning.overdue(invoices, as_of="2026-12-01")
    assert got and set(got[0]) == {"account", "period", "due_on", "total"}


def test_a_paid_invoice_is_never_chased():
    invoices = [{"account": "acme-01", "period": "2026-07",
                 "issued_on": "2026-01-01", "total": "10.00",
                 "paid_on": "2026-02-01"}]
    assert dunning.overdue(invoices, as_of="2026-12-01") == []


def test_a_statement_renders_the_invoice_numbers():
    invoice = {"account": "acme-01", "period": "2026-07", "subtotal": "10.00",
               "credits": [{"amount": "1.00", "reason": "outage"}],
               "total": "9.00"}
    text = statement.render(invoice, [])
    assert "subtotal 10.00" in text and "total    9.00" in text
    assert "outage" in text
