# v0.4 — corrections

**Status: approved 2026-06-30.** Scheduled after v0.3.

## Why

Sites re-send readings. A re-sent row carries `corrects` pointing at the id of
the row it replaces. Today we total both, so a corrected month is wrong.

Worse, the correction usually arrives *after* the month has been reported. The
billing team needs to answer "what did we believe on the 5th?" as well as
"what do we believe now?" — an invoice that was issued against the old number
has to stay explainable.

## What v0.4 adds

1. **Corrections apply.** A row with `corrects: X` replaces row `X` entirely.
   A chain of corrections applies in `recorded_at` order; the last one wins.
   A row that corrects an unknown id is reported as skipped with the reason
   `unknown correction target`.
2. **As-of queries.** Every command takes `--as-of <timestamp>`. Only rows
   whose `recorded_at` is at or before that timestamp are considered. With no
   `--as-of`, everything is considered.
3. **Alerts follow as-of.** An alert list computed as of a past timestamp must
   match what we would have raised then.
4. **Export carries the basis.** The JSON export gains `"as_of"` — the
   timestamp used, or `null`.

## What this needs from the reading record

A reading has to carry **both** timestamps — when the usage happened and when
we learned about it — and its own id, and what it corrects. `observed_at`
alone cannot answer an as-of question, and without ids a correction has
nothing to point at.

The feeds already carry all four fields.
