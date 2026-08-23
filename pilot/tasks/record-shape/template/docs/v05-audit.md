# v0.5 — audit trail

**Status: approved 2026-06-30.** Scheduled after v0.4.

## Why

When the billing team disputes a total, we have to show the rows behind it.
Right now we can only show the total.

## What v0.5 adds

    python -m meterhouse audit --data <dir> --month YYYY-MM --account ACC-1234

Output:

    {
      "account": "ACC-1234",
      "month": "2026-07",
      "quantity": "...",
      "sources": [
        {"id": "a01", "file": "site-a-2026-07.csv", "line": 2,
         "quantity": "...", "superseded_by": null},
        ...
      ]
    }

1. **Every reading names its source** — the file it came from and the line
   number within that file (the first data line is line 2 in a CSV, line 1 in
   a JSONL).
2. **Superseded rows stay in the trail**, marked with the id of the row that
   replaced them. They do not count toward the quantity.
3. **Sources are sorted** by file name then line number.
4. `--as-of` applies here too.

## What this needs from the reading record

Each reading has to carry where it came from. A total that has been summed
cannot be walked back to its rows unless every reading kept its origin.
