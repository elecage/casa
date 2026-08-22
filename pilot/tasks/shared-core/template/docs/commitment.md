# Commitment (billing, part 7)

Some accounts signed for a monthly volume. When an account uses less than it
signed for, the difference is still owed. This reports that gap.

**It does not bill it.** The gap does not go on the invoice yet; operations
wants to look at it for a month first. Nothing in `docs/invoice.md` changes.

## What an account signed for

`contracts.json` carries `committed_units` for the accounts that signed for a
volume. **Not every account did.** An account with no `committed_units` has no
commitment and therefore no gap — reporting one against a number nobody agreed
to is how a customer gets an invoice they did not sign for.

The account name in `contracts.json` is the contract's spelling, the same
problem `docs/rating.md` has.

## What counts as used

**The same units the report counts** (`docs/report.md`): the billed quantity,
in the period, cancelled records left out. The two products read the same
records, so a figure here that disagrees with the report for the same account
and month means one of them is reading them differently.

## The gap

`shortfall_units` is what was signed for less what was used. **An account that
used more than it signed for has a gap of zero, not a negative one.**

`shortfall` is that many units at the account's rate, money to the cent under
the rounding rule settled in `docs/invoice.md`. Commitment does not get a
rounding rule of its own.

## What it must not do

Commitment does not re-answer any question `core` already answers — account
spelling, the month boundary, what a cancelled record counts for, and rounding
are settled once for both products.
