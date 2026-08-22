"""What a cancelled record means. The spec sections are "Cancelled records" in
`docs/report.md` and in `docs/invoice.md`.

A record can be `ok`, `adjusted` or `void`. `void` means the usage was
cancelled after the fact.

**The two products want different things from it.** Operations wants the
cancelled usage out of the totals — it did not happen. Billing has to keep it
on the statement, because the customer was told about it and a line that
disappears between two statements is a support call.

`COUNTS_VOID` decides what `is_billable` says. It does not decide what the
statement shows; that is `docs/invoice.md`'s "Cancelled records" section.
"""

from __future__ import annotations

#: Whether a `void` record counts toward usage totals.
COUNTS_VOID = False
