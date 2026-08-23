# Changelog

## v0.5 — unreleased

- Audit trail: `audit --account` shows the source rows behind a total,
  including superseded rows and what replaced them.

## v0.4 — unreleased

- Corrections apply: a row with `corrects` replaces the row it names, last
  one wins by `recorded_at`. A correction pointing at an unknown id is
  reported as skipped.
- `--as-of` on every command: only rows recorded at or before that moment
  are considered.
- The JSON export carries the `as_of` it was computed with.

## v0.3 — unreleased

- JSONL feed adapter.
- Threshold alerts against `alert-rules.json`.
- CSV export.
- The reading record now carries every field the feeds give us: both
  timestamps, the row id, what it corrects, and where it came from.

## v0.2.1 — 2026-06-24

- Fixed the month boundary in `rollup` (was using local time).

## v0.2 — 2026-06-18

- CSV feed adapter.
- Threshold alerts.

  (An earlier version of this entry claimed source tracking was added here.
  It was not — the change was reverted before release and the entry was
  never corrected. Source tracking landed in v0.3.)

## v0.1 — 2026-05-30

- First cut: read one CSV, print a total.
