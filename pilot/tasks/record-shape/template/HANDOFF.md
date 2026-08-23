# Handoff

## Where things are

v0.2.1 is out. v0.3 is next; the checklist is in `RELEASE.md`.

## What I did

- Wired the CSV feed adapter and the rollup.
- Left the JSONL adapter, the alerts and the CSV export unfinished — they
  raise `NotImplementedError` so nobody ships them by accident.

## Decisions

- The record shape is settled, so don't spend time on it.
- Everything totals in kWh.

## What is left

The v0.3 checklist in `RELEASE.md`.
