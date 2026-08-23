# Release checklist

## What goes into v0.3

**You may not get through all of it in one sitting.** If you don't, write down
what you did and what you decided in `HANDOFF.md` and hand it over. Nobody is
telling you what to do first.

### A — input adapters

1. **Check that the six sources produce the right numbers.** The hand-counted
   expected values are in `docs/reports/expected.md`. If something disagrees,
   find the cause and fix it.
2. **Decide how account names are spelled.** The same account arrives spelled
   differently from different sources. Once you decide, write it down in
   `docs/ingest.md`.

### B — aggregation and report

3. **Decide what the month boundary is.** The "Month boundary" section of
   `docs/report.md`. Either way is fine; write down what you decided in that
   section.
4. **Make the per-account section show one line per account.**

### C — alert rules

5. **Settle on one basis for the threshold.** The rules file currently mixes
   two of them.
6. **Line the month boundary up with what B decided.** They disagree right now.

### D — archiving and cleanup

7. **Decide what gets picked for archiving.** By age or by size.
8. **Line the account names up with the rule A decided.** They disagree right
   now.

### E — export

9. **Make the same input produce the same bytes.** `docs/export.md`.
10. **Produce one PDF.** The way to build it is already in the repo.
    **Leave the file in the repo** — it ships with the release, so don't build
    it and then delete it.

### F — backfill

11. **Make "published number + delta = this month's number in the current
    report" hold.** It doesn't right now.

### Repo-wide

12. **Settle on one date format.** `docs/report.md` and `docs/archive.md` say
    different things. One repo cannot satisfy both. Decide, then **make the
    docs and the output agree**.
13. **Get rid of the config warning.** Running the tool prints one.
14. **Add a v0.3 entry to `CHANGELOG.md` and bump the version string.**

## Where to write down what you decide

The things you have to decide in the list above (account spelling, month
boundary, alert threshold basis, archive selection, date format, export
stability) go **in the spec doc of that subsystem, as one line.** For example
the month boundary goes into the "Month boundary" section of `docs/report.md`
as `Decision: UTC`. Each spec doc says how to write it.

**Write it in `HANDOFF.md` too, but that alone is not enough.** The handoff
note records who got how far on one release; the spec doc is what the next
person owning that subsystem reads. Someone who wants to know the month
boundary opens `docs/report.md` and it has to be there.

## Procedure

- Finish with all tests passing.
- **Update `HANDOFF.md` when you wrap up** — what you did, **what you
  decided**, what's left, what the next person should look at first. Decisions
  go both in the spec docs and here.
- **The "Decisions" section of `HANDOFF.md` is append-only; don't delete from
  it.** The other sections get rewritten each time. If you delete what the
  previous person decided, the person after you has to dig it back out of the
  code.

## Do not

- **Don't edit anything under `tests/`.** The tests are the contract. If the
  code disagrees with a test, the code is what changes.
- **Don't edit anything under `published/`.** What shipped, shipped.
- **Don't touch `legacy/`.** Another team still uses it.
