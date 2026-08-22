# Backfill (subsystem F)

Compares the monthly numbers that already went out with the numbers recounted
from the current samples, and records the difference. The code is in
`opsbox/backfill/`.

## What shipped does not get corrected

The files under `published/` stay exactly as they went out. Whatever changed
is recorded **as a difference**. That way what changed, when, and by how much
stays on record.

## How to check that the difference is right

**Published number + difference = this month's number in the current report.**
If that equation doesn't hold, backfill is doing a different arithmetic than
the report.

## It leans on two things

- **Account names** — use the rule the input adapters (subsystem A) settled on
  (`opsbox.ingest.accounts.normalize_account`). The "Account spelling" section
  of `docs/ingest.md`.
- **Month boundary** — use the basis the aggregation (subsystem B) settled on
  (`opsbox.report.months.month_key`). The "Month boundary" section of
  `docs/report.md`.

**Right now both are worked out here separately.** `_account` and `_month_of`
in `opsbox/backfill/plan.py` are the places. That is why the check above does
not hold.

What the previous person chose for A and B is in each spec doc and in
`HANDOFF.md`.
