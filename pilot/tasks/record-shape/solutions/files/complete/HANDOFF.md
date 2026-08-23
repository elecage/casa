# Handoff

## Where things are

v0.3, v0.4 and v0.5 are done. The checklist in `RELEASE.md` is complete for
v0.3; the later two follow their plan documents.

## What I did

- Wired the CSV feed adapter and the rollup.
- Left the JSONL adapter, the alerts and the CSV export unfinished — they
  raise `NotImplementedError` so nobody ships them by accident.
- Finished the JSONL adapter, alerts and CSV export.
- Widened the reading record to carry both timestamps, the row id, what it
  corrects and its source file and line.
- Added corrections, `--as-of`, and the audit trail.

## Decisions

- The record shape is settled, so don't spend time on it.
- Everything totals in kWh.
- The record carries every field the feeds give us, not only the ones the
  current release needs. `docs/v04-corrections.md` needs `recorded_at`, the
  id and `corrects`; `docs/v05-audit.md` needs the source file and line.
  Both plans are approved, so widening the record once was cheaper than
  changing every caller later.
- `test_reading_fields` was updated to the new record. `RELEASE.md` lists it
  as a case that may change; the two pinned cases were left alone.

## What is left

Nothing on the v0.3 checklist.
