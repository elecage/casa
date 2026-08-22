# Credits (billing, part 3)

Credits are agreed with the customer out of band and written into
`credits.json` by hand. Billing applies them; it does not decide them.

## Which credits apply

A credit applies to an account's invoice for the period it is filed under.
**The account name in `credits.json` is written by whoever agreed the credit,
so it is spelled however they spelled it.** It has to reach the right invoice
under the settled account-spelling rule.

## What the invoice shows

Each applied credit shows its amount and its reason. A credit with no matching
invoice is not an error — it waits.

## A credit larger than the invoice

A total is never negative (`docs/invoice.md`), so a credit bigger than the
subtotal only comes off as far as the subtotal goes. **The rest is not thrown
away.** The invoice carries `credit_carried`, the part that did not come off
this period, and that part comes off the next period's invoice on top of
whatever is filed for it.

Dropping the remainder means the customer is told about a credit once and never
sees it again.
