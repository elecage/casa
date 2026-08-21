# Changelog

## v0.2.3

- Backfill (F) can now produce a per-month difference.
- Export (E) can now produce a one-page PDF.
- Archiving (D) gained a way to pick by size.

## v0.2.2

- Alert rules (C) gained a `basis` key. Existing rules were left alone; only
  new ones use it.
- **Account spelling was pulled into one place** (`opsbox/ingest/accounts.py`).
  What to do about upper and lower case is still undecided.

## v0.2.1

- Input adapters gained the `fh` source.
- Config gained `keep_originals`.

## v0.2.0

- Split into six subsystems.
