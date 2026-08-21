# Backfill (subsystem F)

Compares the monthly numbers that already went out with the numbers recounted
from the current samples, and records the difference. The code is in
`opsbox/backfill/`.

## What shipped does not get corrected

The files under `published/` stay exactly as they went out. Whatever changed
is recorded **as a difference**. That way what changed, when, and by how much
stays on record.

## The two identities that have to hold

**Monthly.** Published total + difference = the month's number in the current
report.

**Per account.** For every account the published file names: published number
for that account + difference for that account = what the current report says
for that account in that month. The published files carry a `by_account`
block; `docs/report.md`'s fifth section is the other side of it.

If either identity does not hold, backfill is doing a different arithmetic
than the report, and the number that goes out next will be wrong in a way
nobody can see from either side alone.

## It leans on two things

- **Account names** — whatever rule the input adapters (subsystem A) settled
  on. The "Account spelling" section of `docs/ingest.md`.
- **Month boundary** — whatever basis the aggregation (subsystem B) settled
  on. The "Month boundary" section of `docs/report.md`.

Neither is decided here. A second copy of either rule is how the identities
above stop holding.

What the previous person chose for A and B is in each spec doc and in
`HANDOFF.md`.
