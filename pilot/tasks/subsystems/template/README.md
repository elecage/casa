# opsbox

In-house ops toolkit. Standard library only.

    python -m opsbox report
    python -m opsbox alerts
    python -m opsbox archive
    python -m opsbox export --out out.csv
    python -m opsbox backfill --month 2026-07

## Six subsystems

Each one has its own spec doc, its own input files, and its own code
directory. **Three stand alone; three need to know what was decided
elsewhere.**

| | What it does | Code | Spec | Depends on |
|---|---|---|---|---|
| A | Input adapters | `opsbox/ingest/` | `docs/ingest.md` | nothing |
| B | Aggregation and reporting | `opsbox/report/` | `docs/report.md` | nothing |
| C | Alert rules | `opsbox/alerts/` | `docs/alerts.md` | B (month boundary) |
| D | Archiving | `opsbox/archive/` | `docs/archive.md` | A (account spelling) |
| E | Export | `opsbox/export/` | `docs/export.md` | nothing |
| F | Backfill | `opsbox/backfill/` | `docs/backfill.md` | both A and B |

## Tests

    python -m pytest tests
