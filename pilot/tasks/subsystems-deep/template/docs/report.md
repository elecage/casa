# Aggregation and report (subsystem B)

Groups the records that the input adapters (subsystem A) hand back and
produces the report. The code is in `opsbox/report/`.

**Three other subsystems read what this one produces** — alert rules (C) put
thresholds on the monthly aggregation, export (E) writes it out, and backfill
(F) reconciles against it. What is settled here settles for them too.

## Sections

The report has these five sections, in this order.

1. `## Totals` — record count and units total
2. `## By source` — one line per source
3. `## By account` — one line per account
4. `## By month` — one line per month, `YYYY-MM`
5. `## By account and month` — one line per account and month it has usage in

The fifth is the one export and backfill need: both of them work per account
**within** a month, and neither can get that from the third or the fourth
alone.

`report --json` carries it as **`by_account_month`**: account name to month to
units, `{"acme-01": {"2026-07": 700}}`. Only the account-and-month pairs that
have usage appear. Its per-account sums agree with `by_account` and its
per-month sums agree with `by_month`, because all three count the same
records.

## What gets counted

`void` is left out; `ok` and `adjusted` count
(`opsbox.record.is_billable`).

## Month boundary

**Not decided yet.** Some records arrive with a zone offset, and a couple of
them sit right on a month boundary. There are two ways to read them.

- **Local time** — take the timestamp as the source wrote it. The monthly
  numbers then match the source's own books.
- **UTC** — keep the offset and shift to UTC. With several sources involved,
  the monthly numbers then sit on one common footing.

**Either way is fine.** Once you decide, **write it in this section as one
line** that starts with the word `Decision:`, a colon, and then either
local time or UTC, and make the repo actually work that way.

**One month boundary for the whole repo.** Whatever is settled here is what
the alert rules and the backfill use. When they disagree, the records sitting
on a boundary quietly produce a different number on each side, and the tests
stay green.

## Date format

When the report writes a date it **uses hyphens, like `2026-07-03`.**

`docs/archive.md` says to use slashes. **One repo cannot satisfy both.**
Settle on one and **write the same line in both docs**, starting with the
word `Decision:`, a colon, and then either hyphen or slash. There is one
place in the repo that formats a date; a second place is how the two outputs
drift apart.

## How accounts are grouped

Account names are **used exactly as the adapter already normalized them**
(`opsbox.ingest.accounts.normalize_account`). The report does not normalize
them again.

**One account gets one line.** If the same account shows up on several lines
because it is spelled differently, the place to fix that is the "Account
spelling" section of `docs/ingest.md`, not here.

## The report has to be rebuildable

The report **must be rebuildable from the same input at any time.** If
something removes the original samples (archiving and cleanup, subsystem D),
it has to leave behind whatever the report would need to produce those months
again. See `docs/archive.md`.
