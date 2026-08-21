# Aggregation and report (subsystem B)

Groups the records that the input adapters (subsystem A) hand back and
produces the report. The code is in `opsbox/report/`.

## Sections

The report has these four sections, in this order.

1. `## Totals` — record count and units total
2. `## By source` — one line per source
3. `## By account` — one line per account
4. `## By month` — one line per month, `YYYY-MM`

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

**Either way is fine.** Once you decide, set `MONTH_BASIS` in
`opsbox/report/months.py` accordingly and **write it in this section as one
line.** `Decision: local time` or `Decision: UTC`.

**What you decide carries into the alert rules (subsystem C).** C puts
thresholds on top of this monthly aggregation. If C uses a different basis,
the records on the boundary quietly produce a different number, and the tests
stay green. See `docs/alerts.md` as well.

## Date format

When the report writes a date it **uses hyphens, like `2026-07-03`.**
`DATE_STYLE` in `opsbox/report/dates.py` is where that lives.

`docs/archive.md` says to use slashes. **One repo cannot satisfy both.**
Settle on one and **write the same line in both docs** —
`Decision: hyphen` or `Decision: slash`.

## How accounts are grouped

Account names are **used exactly as the adapter already normalized them**
(`opsbox.ingest.accounts.normalize_account`). The report does not normalize
them again — once the rule lives in two places, one of them quietly leaves an
account sitting on two lines.

Right now the same account shows up on several lines because it is spelled
differently. The place to fix that is not the report; it is the "Account
spelling" section of `docs/ingest.md`.

## The report has to be rebuildable

The report **must be rebuildable from the same input at any time.** If
something deletes the original samples (archiving and cleanup, subsystem D),
it has to leave a way to rebuild along with it.
