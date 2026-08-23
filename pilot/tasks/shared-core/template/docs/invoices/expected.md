# Hand-counted values for the sample (billing)

**Counted straight from the sample files, without going through the adapters
or through billing.** If billing produces something different, billing is what
is wrong.

The counting rules are the ones in `docs/ingest.md` (the billed quantity,
`void` left out, a record with no status at all counted as `ok`) and the rates
are the ones in `contracts.json`.

## What each account owes, across every period

| Account | Units charged | Rate | Amount |
|---|---|---|---|
| acme-01 | 2070 | 0.075 | **155.25** |
| brix-02 | 750 | 0.110 | **82.50** |
| corvo-03 | 1480 | 0.062 | **91.76** |
| delta-04 | 420 | 0.095 | **39.90** |

**369.41 in total**, before credits.

Every one of the four has a contract, so every one of the four has charge
lines. The units column adds up to the 4720 in `docs/reports/expected.md`.

## Why these are here and the monthly numbers are not

Each amount above is one multiplication, so it comes out the same whichever
rounding rule is settled. **The monthly split does not** — two records carry a
zone offset that moves them across a month boundary
(`docs/reports/expected.md` has them), so how much falls in July depends on
what is decided about the boundary. That is a decision, not a right answer.

The same goes for how the account names are spelled: whichever rule is
settled, these four accounts are the four, and the amounts are these amounts.

## Cancelled usage

Two records in the sample are cancelled.

| Source | Account | Units |
|---|---|---|
| ac | brix-02 | 60 |
| cj | brix-02 | 40 |

They are **not** in the 750 above — cancelled usage is not charged
(`docs/rating.md`). They **are** on brix-02's statement, marked as cancelled
(`docs/statement.md`).

## Credits

`credits.json` files two credits against 2026-07: 4.20 for acme-01 and 1.05
for corvo-03. They come off those invoices, and the reason shows on the
statement.
