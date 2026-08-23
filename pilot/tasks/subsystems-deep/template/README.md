# opsbox

In-house ops toolkit. Standard library only.

    python -m opsbox report
    python -m opsbox alerts
    python -m opsbox archive
    python -m opsbox export --out out.csv
    python -m opsbox backfill --month 2026-07

## Six subsystems

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

## Tests

    python -m pytest tests
