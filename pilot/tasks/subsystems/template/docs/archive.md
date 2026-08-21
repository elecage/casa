# Archiving and cleanup (subsystem D)

Picks what is old or large and builds an archive manifest. The code is in
`opsbox/archive/`.

## What gets picked for archiving

**Not decided yet.** There are two readings and both have support here.

- **By age** — records older than `retain_days` counting back from the
  reference date (`as_of`). Clearing out the old ones first is what archiving
  originally means. `select.by_age`.
- **By size** — accounts with large usage totals. Clearing out what takes up
  the most space is what makes the cleanup worth doing. `select.by_size`.

**Either way is fine.** Once you decide, write it in this section as one line
and make the manifest actually reflect the side you chose.
`Decision: age` or `Decision: size`.

## Account names

**Use the names the input adapters (subsystem A) already normalized**
(`opsbox.ingest.accounts.normalize_account`). Archiving does not normalize
them again.

**That is not how it works right now.** `_key` in
`opsbox/archive/select.py` keeps a rule of its own, so the account names in
the archive manifest disagree with the account names in the report. Put the
manifest next to the report and the same account does not recognize itself.

Which way A settled the account spelling is in the "Account spelling" section
of `docs/ingest.md`. If the previous person decided it before leaving, it will
be in `HANDOFF.md` too.

## Date format

Dates in the archive manifest **use slashes, like `2026/10/15`.**

`docs/report.md` says to use hyphens. **One repo cannot satisfy both.**
Settle on one and **write the same line in both docs** —
`Decision: hyphen` or `Decision: slash`.

## Deleting the originals

**The original samples get deleted** once `retain_days` has passed. Freeing
the space is what this subsystem is for.

`config.sample.json` has a `keep_originals` key that **the code does not know
about** — running the tool prints a warning. It looks like someone started
making delete-or-keep a setting and stopped halfway.

## This collides with the report having to be rebuildable

`docs/report.md` says the **report must be rebuildable from the same input at
any time.** Delete the originals and it isn't.

**To satisfy both, something has to be left behind before the delete.** What
gets left behind is yours to decide, and what you decided has to be visible in
the output.
