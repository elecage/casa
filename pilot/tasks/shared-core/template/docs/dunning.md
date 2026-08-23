# Dunning (billing, part 5)

Which invoices are past due.

## When an invoice falls due

Terms days after it was issued. The terms are in `contracts.json` and differ by
account. **The account name there is the contract's spelling**, the same
problem `docs/rating.md` has.

An account with no contract is not chased.

## What counts as overdue

Past the due date and not paid. An invoice carries `paid_on` when it has been
paid; those are never chased however old they are.

**`paid_on` is not the only way an invoice gets paid, and nothing sets it.**
What the customer has actually sent is in `payments.json` and is worked out by
`docs/payments.md`. An invoice whose balance is zero there is settled and is not
chased, whether or not it carries `paid_on`.

**Due dates are dates, not moments.** An invoice due on the 30th is not overdue
on the 30th.

## What it reports

For each overdue invoice: the account, the period, the due date, and the
amount. Nothing else — this list goes to a person who then makes a phone call.
