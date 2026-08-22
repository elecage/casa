"""Billing. Turns the same usage records into what each account owes.

Six pieces, each with a spec doc under `docs/`:

    rating       usage records -> charge lines        docs/rating.md
    invoice      charge lines -> one invoice          docs/invoice.md
    credits      agreed credits come off an invoice   docs/credits.md
    statement    what the customer reads              docs/statement.md
    dunning      which invoices are overdue           docs/dunning.md
    reconcile    billing against operations           docs/reconcile.md

**Everything about a timestamp, a month, an account name or a rounding rule
comes from `core`.** Billing does not get its own answer to those — operations
reads the same records and the two have to agree. `README.md` has the table.
"""
