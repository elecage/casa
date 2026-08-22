# opsbox + billsy

Two products over one set of usage records. Standard library only.

    python -m opsbox report
    python -m opsbox alerts
    python -m opsbox archive
    python -m opsbox export --out out.csv
    python -m opsbox backfill --month 2026-07

    python -m billsy invoice --account acme-01 --period 2026-07 --json
    python -m billsy statement --account acme-01 --period 2026-07
    python -m billsy dunning --as-of 2026-09-01
    python -m billsy reconcile --month 2026-07
    python -m billsy payments --account acme-01 --period 2026-07

## The shared core

`core/` holds the four things both products have to agree on: how a timestamp
is read, where the month boundary goes, how an account name is spelled, and how
money is rounded. **Neither product gets its own answer to those.** When one of
them grew a second copy the two drifted and nothing raised.

| | Code | Spec |
|---|---|---|
| Timestamps | `core/timeparse.py` | `docs/ingest.md` |
| Month boundary | `core/months.py` | `docs/report.md` |
| Account spelling | `core/accounts.py` | `docs/ingest.md` |
| Rounding | `core/money.py` | `docs/invoice.md` |
| Cancelled records | `core/status.py` | `docs/report.md`, `docs/statement.md` |

## opsbox — six subsystems

Each one has its own spec doc, its own input files, and its own code
directory. The spec doc is the contract; this table is a map, and it was last
touched when the split happened in v0.2.0.

| | What it does | Code | Spec | Depends on |
|---|---|---|---|---|
| A | Input adapters | `opsbox/ingest/` | `docs/ingest.md` | nothing |
| B | Aggregation and reporting | `opsbox/report/` | `docs/report.md` | nothing |
| C | Alert rules | `opsbox/alerts/` | `docs/alerts.md` | B |
| D | Archiving | `opsbox/archive/` | `docs/archive.md` | A |
| E | Export | `opsbox/export/` | `docs/export.md` | nothing |
| F | Backfill | `opsbox/backfill/` | `docs/backfill.md` | A |

## billsy — seven subsystems

| | What it does | Code | Spec | Depends on |
|---|---|---|---|---|
| G | Rating | `billsy/rating.py` | `docs/rating.md` | A |
| H | Invoice | `billsy/invoice.py` | `docs/invoice.md` | G, I |
| I | Credits | `billsy/credits.py` | `docs/credits.md` | nothing |
| J | Statement | `billsy/statement.py` | `docs/statement.md` | H |
| K | Dunning | `billsy/dunning.py` | `docs/dunning.md` | H |
| L | Reconcile | `billsy/reconcile.py` | `docs/reconcile.md` | B, G |
| M | Payments | `billsy/payments.py` | `docs/payments.md` | H |

## Tests

    python -m pytest tests
