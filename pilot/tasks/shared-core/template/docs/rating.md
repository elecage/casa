# Rating (billing, part 1)

Turns usage records into charge lines. One line per account per billing
period: how many units, at what rate, for how much.

## What a line has to say

| field | what it is |
|---|---|
| `account` | the account, spelled the way the settled rule spells it |
| `month` | the billing period, `2026-07` form |
| `units` | the units being charged for |
| `rate` | the rate from `contracts.json` |
| `amount` | units × rate |

## Every account with a contract gets a line

If an account has a contract in `contracts.json` and has usage in the period,
it has a charge line. **The contract writes account names the way the customer
writes them, and the sources write them their own way.** Whatever rule is
settled for account spelling, the two have to meet under it.

An account with usage but no contract is not charged. That is not an error.

## Cancelled usage is not charged

A record whose status is `void` was cancelled. **It is not units the customer
owes for.** What the statement shows about it is `docs/statement.md`'s
business, not this one's.

## Rounding

`amount` is money and follows the rounding rule in `core`. See "Rounding" in
`docs/invoice.md` for which rule that is and what has to be settled.
