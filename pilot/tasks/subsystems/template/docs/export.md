# Export (subsystem E)

Puts the report into a shape the outside can read. The code is in
`opsbox/export/`. **It does not lean on any other subsystem's decision** — it
copies out the report it was handed.

## The flat table

Column order is `account,month,units`. The first line is the column names.

## The same input must produce the same bytes

**Export the same thing twice and the two files must be identical down to the
bytes.** The team on the other end takes this and diffs it against the
previous one; if it differs every time it is exported, there is nothing to
diff.

**That is not the case right now.** `opsbox/export/flat.py` writes **the time
of export** on the first line. One second apart and it is a different file.

There is more than one way to fix it. Dropping that line works, and so does
changing the timestamp from the time of export to **the reference date of the
data** (`as_of` in `config`). **Either way is fine**; write what you decided
in this section as one line. `Decision: drop the timestamp line` or
`Decision: use the as-of date`.

## One PDF

Built with `vendor/minipdf.py`. It was vendored into the repo from outside, so
it needs neither the network nor `pip install`. See `vendor/README.md`.
