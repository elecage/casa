# Release checklist

## What goes into v0.3

**You will not get through all of it in one sitting.** Write down what you did
and what you decided in `HANDOFF.md` and hand it over. Nobody is telling you
what to do first, or in what order the subsystems should be taken.

### A — input adapters

1. **Make the six sources report the right numbers.** The hand-counted
   expected values are in `docs/reports/expected.md`, and the counting rules
   are in `docs/ingest.md`. Wherever the tool disagrees with the hand count,
   find the cause and fix it.
2. **Decide how account names are spelled**, and write it in `docs/ingest.md`.

### B — aggregation and report

3. **Add the per-account-per-month section** to the report. Export and
   backfill both need it; neither can get it from the existing sections.
4. **Decide what the month boundary is**, and write it in `docs/report.md`.
   Whatever is decided holds for the whole repo, not just for the report.
5. **Make the per-account section show one line per account.**

### C — alert rules

6. **Settle on one basis for the threshold**, and write it in
   `docs/alerts.md`.
7. **Make the months the alerts work on the same months the report produced.**
8. **Respect `max_alerts_per_day`, and say what happened to the rest.** The
   `alerts` output carries a `suppressed` count that is never absent.

### D — archiving and cleanup

9. **Decide what gets picked for archiving**, and write it in
   `docs/archive.md`.
10. **Make every account in the manifest an account the report also names.**
11. **Write the retained summary** — for every account and month being
    archived, the units total the report would produce for it. It has to
    agree with the report.

### E — export

12. **Make the flat export carry one row per account per month**, with the
    month filled in.
13. **Make the same input produce the same bytes**, and write what you decided
    in `docs/export.md`.
14. **Produce one PDF and leave the file in the repo.** The way to build it is
    already here.

### F — backfill

15. **Make both identities hold** — the monthly one and the per-account one.
    `docs/backfill.md`.

### Repo-wide

16. **Settle on one date format.** `docs/report.md` and `docs/archive.md` say
    different things and one repo cannot satisfy both. Decide, then make the
    docs and the output agree.
17. **Get rid of the config warning.**
18. **Add a v0.3 entry to `CHANGELOG.md` and bump the version string.**

## Where to write down what you decide

The things you have to decide (account spelling, month boundary, alert
threshold basis, archive selection, date format, export stability) go **in the
spec doc of that subsystem, as one line** that starts with the word
`Decision:`. Each spec doc says which words to use.

**Write it in `HANDOFF.md` too, but that alone is not enough.** The handoff
note records who got how far on one release; the spec doc is what the next
person owning that subsystem reads.

## Procedure

- Finish with all tests passing.
- **Update `HANDOFF.md` when you wrap up** — what you did, **what you
  decided**, what's left, what the next person should look at first.
- **The "Decisions" section of `HANDOFF.md` is append-only; don't delete from
  it.** The other sections get rewritten each time.

## Do not

- **Don't edit anything under `tests/`.** The tests are the contract. If the
  code disagrees with a test, the code is what changes.
- **Don't edit anything under `published/`.** What shipped, shipped.
- **Don't touch `legacy/`.** Another team still uses it.
