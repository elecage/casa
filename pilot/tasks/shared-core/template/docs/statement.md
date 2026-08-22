# Statement (billing, part 4)

What the customer reads. The invoice plus the usage behind it, so a person can
check it against their own records.

## Cancelled records stay on the statement

A cancelled record is not charged for (`docs/rating.md`). **It still appears on
the statement**, marked as cancelled, because the customer was told about that
usage when it happened. A line that is on one statement and gone from the next
is a support call.

So the statement shows every record in the period, and the ones that were
cancelled are shown as cancelled and contribute nothing to the amounts.

## Order

Oldest first. Two runs over the same records produce the same order.

## Amounts

Subtotal, then each credit on its own line, then the total. The numbers are the
invoice's numbers — the statement does not add anything up for itself.
