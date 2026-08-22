# Input adapters (subsystem A)

Reads the files under `data/` and hands back a list of
`opsbox.record.Record`. No aggregation and no sorting happens here. The code
is in `opsbox/ingest/`.

## The six sources

| Source | File | Format |
|---|---|---|
| ac | `ac-*.csv` | Comma separated. Columns are `account,at,units,status` |
| bd | `bd-*.tsv` | Tab separated. Columns are `account,at,qty,qty_billed,status` |
| cj | `cj-*.jsonl` | One JSON object per line. Keys are `acct,ts,units,state` |
| df | `df-*.txt` | Fixed-width table. See "Column positions (df)" below |
| eg | `eg-*.txt` | `key=value` pairs, several per line |
| fh | `fh-*.csv` | Comma separated. Columns are `customer,when,amount,flag` |

## What the adapters must produce

**The hand-counted values for the current sample are in
`docs/reports/expected.md`.** They were counted straight from the files
without going through the adapters. What the tool reports has to match them.

The rules the hand count used are the ones below. When the tool and the hand
count disagree, the tool is what's wrong.

### Which quantity counts

**The billed quantity.** If a source gives only one quantity, that one is the
billed quantity. If a source gives more than one, the billed one is the one to
count — the others are what the figure was before a correction or a cap.

### Which records count

There are three statuses: `ok`, `adjusted`, `void`.

- `void` is left out of the totals.
- `adjusted` was corrected after the fact and counts.
- **A record that carries no status at all counts as `ok`.** Not every source
  writes the status on every line. A missing status is not a reason to leave
  the record out — the usage happened either way.

`opsbox.record.is_billable` is the one place that decides this.

### Column positions (df)

Positions are 0-based and the end position is not included.

| Column | Start | End | Note |
|---|---|---|---|
| account | 0 | 10 | left aligned |
| at | 10 | 29 | `YYYY-MM-DDTHH:MM:SS`, 19 characters |
| units | 29 | 35 | right aligned, six characters |
| status | 36 | 44 | left aligned |

If the sample changes, check this table along with it.

## Account spelling

**The same account arrives spelled differently from different sources.** The
case differs, and some sources send surrounding whitespace. For example
`acme-01`, `ACME-01` and ` Acme-01 ` are all the same account.

**One rule, in one place.** `opsbox.ingest.accounts.normalize_account` is that
place; nothing else in the repo normalizes account names again. Once the rule
lives in two places, one of them quietly leaves an account sitting on two
lines.

**What the rule is has not been decided.** Whitespace is stripped; what to do
about the case is open. Either way is fine.

**Once you decide, write it in this section as one line** that starts with
the word `Decision:`, a colon, and then either lowercase or uppercase. If it
isn't written down, the next person has to read the code to find out.

Leaving the spelling as it arrives is not one of the choices: the report gives
one account one line, and several spellings cannot do that.

Everything downstream that names an account uses whatever this rule produces.

## Record timestamps

Use `opsbox._internal.timeparse.parse_ts`. Every source spells the timestamp
differently, so adapters that each parse it themselves drift apart. Some
records carry a zone offset; `parse_ts` drops it and reads the timestamp as
local time. Where UTC is wanted there is a separate `to_utc` — which of the
two applies is decided in `docs/report.md`.
