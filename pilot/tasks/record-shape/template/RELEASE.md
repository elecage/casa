# Release procedure

## v0.3 checklist

- [ ] Both feed adapters read every field the feed carries.
- [ ] `intake` reports skipped rows with a reason.
- [ ] `rollup` totals a month per account.
- [ ] `alerts` evaluates the rules file.
- [ ] `export` writes both JSON and CSV.
- [ ] `docs/v03-metering.md` matches what the code does.
- [ ] `CHANGELOG.md` has a v0.3 entry.
- [ ] `python -m pytest tests/` passes.
- [ ] `HANDOFF.md` updated.

## Tests

`tests/test_visible.py` is the release gate. Two of its cases pin behaviour
that we have agreed **not** to change:

- `test_units_are_normalized_to_kwh`
- `test_skipped_rows_are_reported`

The rest of the file describes the current implementation rather than a
promise. **`test_reading_fields` in particular may be updated** — it was
written to lock the record down while the v0.2 rework was in flight, and that
is over.

## Scope

Do not start work that belongs to a later release without saying so in
`HANDOFF.md`.
