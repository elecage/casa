# Payments (billing, part 6)

What the customer has already paid against an invoice, and what is still owed.

## Which period a payment settles

**A payment settles the period it is filed under in `payments.json`**, which is
the key it sits beneath. The day it arrived is a separate fact: a payment for
September usually arrives in October, and one that arrives in the same month is
not a payment for that month's successor.

Filing a payment by the month it arrived in puts it against an invoice the
customer was not paying.

## Which account a payment belongs to

**The bank writes the account name the way it appears on the transfer.** That
is a third spelling, on top of the one the sources use and the one
`contracts.json` uses — it differs in case and it sometimes has a space where
the others have a hyphen. A payment has to reach the right account under the
settled account-spelling rule (`docs/ingest.md`), and that rule lives in `core`
for both products.

## What the result carries

For one account and one period:

| Field | What it is |
|---|---|
| `account` | the account, spelled the settled way |
| `period` | the billing period settled |
| `invoiced` | the invoice total for that period (`docs/invoice.md`) |
| `paid` | the payments that settle that period, added up |
| `balance` | what is still owed |
| `payments` | each payment: amount, the day it arrived, the bank's reference |

`paid` and `balance` are money to the cent, under the rounding rule settled in
`docs/invoice.md`. Payments do not get a rounding rule of their own.

## Paying more than the invoice

`balance` is never negative. When the payments come to more than the invoice,
the balance is zero and the excess is dealt with — and there are two ways the
trade deals with it. **Send the excess back**, or **hold it as a credit against
the next period.**

Settle it and write it in this section as one line that starts with the word
`Decision:` followed by a colon and either `refund` or `credit`. Then make the
result carry the excess under that name: a field called `refund` or a field
called `credit`, holding the amount, on the account that overpaid and on no
other. A `Decision:` line the code does not follow is worse than none.

## What it must not do

Payments do not re-answer any question `core` already answers. Account
spelling, the month boundary and rounding are settled once for both products.
