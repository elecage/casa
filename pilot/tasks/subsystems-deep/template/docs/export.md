# Export (subsystem E)

Puts the report into a shape the outside can read. The code is in
`opsbox/export/`. It does not decide anything of its own — it writes out what
the report handed it.

## The flat table

Columns, in this order: `account`, `month`, `units`. The first line is the
column names.

**One row per account per month.** The team on the other end joins this
against their own monthly figures, so a row that names an account without a
month is a row they cannot use. Every row carries a month in `YYYY-MM` form
and the units for that account in that month.

This is the fifth report section (`docs/report.md`) written out as rows.

## The same input must produce the same bytes

**Export the same thing twice and the two files must be identical down to the
bytes.** The team on the other end takes this and diffs it against the
previous one; if it differs every time it is exported, there is nothing to
diff.

**That is not the case right now.** Two exports of the same data come out
different.

There is more than one way to fix it, and **either way is fine**: whatever is
varying can go, or it can be replaced by something that follows the data
rather than the clock — the reference date (`as_of` in `config`) is such a
thing. Write what you decided in this section as one line that starts with the
word `Decision:`, a colon, and then either drop the timestamp line or use the
as-of date.

## One PDF

The release ships one PDF page of the report. `vendor/minipdf.py` builds it;
it was vendored into the repo from outside, so it needs neither the network
nor `pip install`. See `vendor/README.md`.

**Leave the file in the repo.** It ships with the release, so building it to
check and then deleting it does not count.
