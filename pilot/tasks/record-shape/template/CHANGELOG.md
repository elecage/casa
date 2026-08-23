# Changelog

## v0.2.1 — 2026-06-24

- Fixed the month boundary in `rollup` (was using local time).

## v0.2 — 2026-06-18

- Added source tracking: every reading now records the file and line it came
  from, so a total can be walked back to its rows.
- CSV feed adapter.
- Threshold alerts.

## v0.1 — 2026-05-30

- First cut: read one CSV, print a total.
