# Hand-counted values for the sample (2026-07)

**These were counted straight from the sample files, without going through the
adapters.** If the tool produces something different, the tool is what's
wrong.

The counting rules are the ones in `docs/ingest.md` — `void` is left out,
`ok` and `adjusted` count. For bd, the billed quantity (`qty_billed`) is what
gets counted.

## By source

| Source | Records | Units total |
|---|---|---|
| ac | 5 | 540 |
| bd | 5 | 635 |
| cj | 4 | 370 |
| df | 4 | 2485 |
| eg | 3 | 305 |
| fh | 3 | 285 |

**24 records, 4620 in total.**

## What is deliberately not here

**No monthly numbers.** They depend on whether the month boundary is taken in
local time or in UTC, and that is something to be decided, not something with
a right answer (the "Month boundary" section of `docs/report.md`). The
per-source values above come out the same either way.

**No per-account numbers either.** How many lines there are depends on how the
account spelling is normalized (the "Account spelling" section of
`docs/ingest.md`). **Whichever way it is decided, though, the per-account
totals must still add up to the 4620 above.**

## Records sitting on a month boundary

Two records in `cj` carry a zone offset that moves them across a month
boundary.

| As the source wrote it | In local time | In UTC | Units |
|---|---|---|---|
| `2026-07-01T00:30:00+09:00` | 2026-07 | 2026-06 | 70 |
| `2026-08-01T02:00:00+09:00` | 2026-08 | 2026-07 | 65 |

Whichever way it is decided, **only one of the two** lands in July.
