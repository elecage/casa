# Reconcile (billing, part 6)

Billing against operations, for one month.

## Why this exists

The two products read the same records. **For any month, the units operations
reports and the units billing charged for have to be the same number, account
by account.** When they are not, one of the two is reading the records
differently and an invoice went out wrong.

This is the check that catches a fix made on one side only.

## What the result carries

| key | what it is |
|---|---|
| `month` | the month checked |
| `matches` | true when every account agrees |
| `by_account` | account -> `{"operations": n, "billing": n}` |
| `disagree` | the accounts where the two numbers differ |

`matches` is true exactly when `disagree` is empty.

## Which accounts

Every account that either side has a number for. An account operations knows
about and billing does not is a disagreement, not an omission.

## Not written yet

The code raises. `RELEASE.md` has it as an item.
