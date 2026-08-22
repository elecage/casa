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
