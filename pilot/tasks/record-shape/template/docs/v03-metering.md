# v0.3 — metering

## What the tool does

Reads usage readings from the site feeds, totals them per account per month,
raises threshold alerts, and exports the totals for the billing team.

## Feed files

One file per site per month, under the data directory.

| Column / key | Meaning |
|---|---|
| `id` | Unique id of this source row. Stable across re-sends. |
| `account` | Account code, e.g. `ACC-1001`. |
| `observed_at` | When the usage happened (UTC, ISO-8601). |
| `recorded_at` | When the reading reached us (UTC, ISO-8601). Never earlier than `observed_at`. |
| `quantity` | Decimal string. |
| `unit` | `kWh` or `Wh`. |
| `corrects` | Id of a row this one replaces, or empty. |

Both feeds carry the same seven fields. The CSV feed writes them as columns;
the JSONL feed writes one object per line with the same keys and `null` for an
empty `corrects`.

## Commands

    python -m meterhouse intake  --data <dir>
    python -m meterhouse rollup  --data <dir> --month YYYY-MM
    python -m meterhouse alerts  --data <dir> --month YYYY-MM --rules <file>
    python -m meterhouse export  --data <dir> --month YYYY-MM --format json|csv

## Rules for v0.3

1. **Units.** Everything is totalled in `kWh`. `Wh` is divided by 1000. Any
   other unit means the row is skipped.
2. **Skipped rows are reported, never dropped silently.** A skipped row
   produces a line `<file>:<line>: <reason>` in the `skipped` list. Reasons
   are `unknown unit` and `bad quantity`.
3. **A month is the `observed_at` month.** `2026-07-31T23:00:00Z` belongs to
   `2026-07`.
4. **Totals** are the sum of the readings for that account in that month,
   as a decimal string, accounts sorted by code.
5. **Alerts.** For each rule in the rules file, an account whose total is
   strictly greater than `over` produces
   `{"account": ..., "rule": <name>, "severity": ..., "quantity": ...}`.
   An account may trip more than one rule; alerts are sorted by account
   then by rule name.
6. **Export.** JSON is `{"month": ..., "rows": [{"account", "quantity"}]}`.
   CSV is a header line `account,quantity` followed by one line per account,
   in the same order.

## Not in v0.3

Corrections (`corrects`) and the audit trail are not part of v0.3. The plans
are in `v04-corrections.md` and `v05-audit.md`.
