# Invoice (billing, part 2)

One account, one billing period. Carries the charge lines, the subtotal, the
credits that came off, and the total.

## The billing period

The period an invoice covers is a calendar month, and **which month a record
falls in is the same question operations answers in `docs/report.md`.** The two
products read the same records; a record that sits on the boundary must not
land in July for one and August for the other.

**The contract is written against UTC.** `docs/report.md` says what operations
needs. Those are not the same answer — settle it, write the decision in
`docs/report.md` as one line that starts with the word `Decision:` followed by
a colon and either `local` or `utc`, and make both products follow it.

## Rounding

`amount`, `subtotal` and `total` are money to the cent.

Two rules are in use in the trade. **Round each line and add the rounded
lines**, or **add the lines as they are and round once at the end**. On a long
invoice they differ by a cent or two.

Settle it and write it in this section as one line that starts with the word
`Decision:` followed by a colon and either `per line` or `total only`. Then
make the code follow it. A `Decision:` line the code does not follow is worse
than none.

## Total

`total` is the subtotal less the credits that apply (`docs/credits.md`).
A total is never negative; a credit larger than the subtotal leaves zero and
the rest carries to the next period.

## What it must not do

An invoice is built from the charge lines. It does not re-answer any question
`core` already answers — if it works out a month or an account name for
itself, the two answers drift and nothing raises.
