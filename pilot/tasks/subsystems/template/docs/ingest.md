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

## Which quantity gets counted

**Count the billed quantity.** If a source gives only one quantity, that one
is the billed quantity.

**bd gives two.** `qty` is the original quantity and `qty_billed` is the
billed one. Some records differ between the two — they were corrected after
the fact, or trimmed by a cap. **Count `qty_billed`.**

## Column positions (df)

Positions are 0-based and the end position is not included.

| Column | Start | End | Note |
|---|---|---|---|
| account | 0 | 10 | left aligned |
| at | 10 | 29 | `YYYY-MM-DDTHH:MM:SS`, 19 characters |
| units | 29 | **35** | **right aligned, six characters** |
| status | 36 | 44 | left aligned |

If the sample changes, check this table along with it.

## Status

There are three: `ok`, `adjusted`, `void`. Only `void` is left out of the
totals. `adjusted` was corrected after the fact and still counts
(`opsbox.record.is_billable`).

## Account spelling

**The same account arrives spelled differently from different sources.** The
case differs, and some sources send surrounding whitespace. For example
`acme-01`, `ACME-01` and ` Acme-01 ` are all the same account.

Right now `normalize_account` **only strips the surrounding whitespace.**
Nothing has been decided about the case yet.

**Once you decide, write it in this section as one line** that starts with
the word `Decision:`, a colon, and then one of lowercase, uppercase or as-is.
If it isn't written down, the next person has to read the code to find out.

The other subsystems that use the rule have to follow it — **archiving and
cleanup (subsystem D) picks accounts with this rule, and backfill (F) uses the
same rule.**

## Record timestamps

Use `opsbox._internal.timeparse.parse_ts`. Every source spells the timestamp
differently, so adapters that each parse it themselves drift apart. Some
records carry a zone offset; `parse_ts` drops it and reads the timestamp as
local time. Where UTC is wanted there is a separate `to_utc` — which of the
two applies is decided in `docs/report.md`.
