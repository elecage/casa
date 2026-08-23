# meterhouse

Usage metering for the billing pipeline. Reads the site feeds, totals usage
per account per month, raises threshold alerts, and exports for billing.

    python -m meterhouse rollup --data data --month 2026-07

## Layout

| Path | What |
|---|---|
| `meterhouse/record.py` | the reading record every module passes around |
| `meterhouse/intake/` | one adapter per feed format |
| `meterhouse/corrections.py` | corrections and as-of resolution |
| `meterhouse/rollup.py` | monthly totals |
| `meterhouse/alerts.py` | threshold alerts |
| `meterhouse/export.py` | export for billing |
| `meterhouse/audit.py` | audit trail |
| `meterhouse/cli.py` | command line |
| `data/` | sample feed files |
| `tests/` | the tests we run before a release |

## Documents

| Document | What | State |
|---|---|---|
| `docs/v03-metering.md` | metering — units, totals, alerts, export | current |
| `docs/v04-corrections.md` | corrections and as-of queries | approved |
| `docs/v05-audit.md` | audit trail | approved |

## Releasing

`RELEASE.md` has the checklist.
