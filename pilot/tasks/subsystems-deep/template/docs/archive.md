# Archiving and cleanup (subsystem D)

Picks what is old or large, writes a manifest, and leaves behind what the
report needs once the originals go. The code is in `opsbox/archive/`.

## What gets picked for archiving

**Not decided yet.** There are two readings and both have support here.

- **By age** — records older than `retain_days` counting back from the
  reference date (`as_of`). Clearing out the old ones first is what archiving
  originally means. `select.by_age`.
- **By size** — accounts with large usage totals. Clearing out what takes up
  the most space is what makes the cleanup worth doing. `select.by_size`.

**Either way is fine.** Once you decide, write it in this section as one
line that starts with the word `Decision:`, a colon, and then either age or
size, and make the manifest actually reflect the side you chose.

## Account names

**Use the names the input adapters (subsystem A) produced**
(`opsbox.ingest.accounts.normalize_account`). Archiving does not normalize
them again.

**Every account named in the manifest has to be an account the report names.**
Put the manifest next to the report and the same account has to recognize
itself. Which way A settled the spelling is in the "Account spelling" section
of `docs/ingest.md`.

## Date format

Dates in the archive manifest **use slashes, like `2026/10/15`.**

`docs/report.md` says to use hyphens. **One repo cannot satisfy both.**
Settle on one and **write the same line in both docs**, starting with the
word `Decision:`, a colon, and then either hyphen or slash.

## Deleting the originals, and the report staying rebuildable

**The original samples get deleted** once `retain_days` has passed. Freeing
the space is what this subsystem is for.

`docs/report.md` says the **report must be rebuildable from the same input at
any time.** Delete the originals and it isn't. Both of these are requirements
and they pull against each other.

**So something has to be left behind before the originals go.** A retained
summary: for every account and month that is being archived, the units total
the report would have produced for it. The `archive` command writes it next to
the manifest, and **its numbers have to match what the report says for those
same accounts and months** — a summary that disagrees with the report is worse
than no summary, because it looks like a record.

The shape is up to you as long as it is machine-readable and the account and
month can be read back out of it.

`config.sample.json` has a `keep_originals` key that **the code does not know
about** — running the tool prints a warning. It looks like someone started
making delete-or-keep a setting and stopped halfway.
