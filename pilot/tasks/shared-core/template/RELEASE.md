# Release checklist

## What goes into v0.4

**You will not get through all of it in one sitting.** Write down what you did
and what you decided in `HANDOFF.md` and hand it over. Nobody is telling you
what to do first, or in what order the subsystems should be taken.

### A — input adapters

1. **Make the six sources report the right numbers.** The hand-counted
   expected values are in `docs/reports/expected.md`, and the counting rules
   are in `docs/ingest.md`. Wherever the tool disagrees with the hand count,
   find the cause and fix it.
2. **Decide how account names are spelled**, and write it in `docs/ingest.md`.

### B — aggregation and report

3. **Add the per-account-per-month section** to the report. Export and
   backfill both need it; neither can get it from the existing sections.
4. **Decide what the month boundary is**, and write it in `docs/report.md`.
   Whatever is decided holds for the whole repo, not just for the report.
5. **Make the per-account section show one line per account.**

### C — alert rules

6. **Settle on one basis for the threshold**, and write it in
   `docs/alerts.md`.
7. **Make the months the alerts work on the same months the report produced.**
8. **Respect `max_alerts_per_day`, and say what happened to the rest.** The
   `alerts` output carries a `suppressed` count that is never absent.

### D — archiving and cleanup

9. **Decide what gets picked for archiving**, and write it in
   `docs/archive.md`.
10. **Make every account in the manifest an account the report also names.**
11. **Write the retained summary** — for every account and month being
    archived, the units total the report would produce for it. It has to
    agree with the report.

### E — export

12. **Make the flat export carry one row per account per month**, with the
    month filled in.
13. **Make the same input produce the same bytes**, and write what you decided
    in `docs/export.md`.
14. **Produce one PDF and leave the file in the repo.** The way to build it is
    already here.

### F — backfill

15. **Make both identities hold** — the monthly one and the per-account one.
    `docs/backfill.md`.

### Repo-wide

16. **Settle on one date format.** `docs/report.md` and `docs/archive.md` say
    different things and one repo cannot satisfy both. Decide, then make the
    docs and the output agree.
17. **Get rid of the config warning.**
18. **Add a v0.3 entry to `CHANGELOG.md` and bump the version string.**

### G — rating

19. **Give every account with a contract a charge line.** `contracts.json`
    writes the names the way the customer writes them; the sources write them
    their own way. Right now one account with a contract and usage gets no
    line at all.
20. **Stop charging for cancelled usage.** `docs/rating.md` says what a `void`
    record is worth.
21. **Make `amount` money to the cent.**

### H — invoice

22. **Settle the rounding rule** and write it in `docs/invoice.md`.
23. **Make the subtotal and total follow the settled rule.**
24. **Make the billing period the same question operations answers.** The
    contract is written against UTC; `docs/report.md` says what operations
    needs. One answer, both products.
25. **Stop the invoice working out a month for itself.** `core` already
    answers it.
26. **A total is never negative.**

### I — credits

27. **Make a credit reach the right invoice** whatever spelling it was filed
    under.
28. **Show each applied credit's amount and reason on the invoice.**
29. **Stop throwing away the part of a credit that did not fit**, and make it
    come off the next period. `docs/credits.md`.

### J — statement

30. **Keep cancelled records on the statement**, marked as cancelled.
31. **Make two runs over the same records produce the same statement.**
32. **Show what has been paid and what is still owed.** `docs/statement.md`.

### K — dunning

33. **Use each account's own terms**, whatever spelling the contract uses.
34. **Don't chase an account that has no contract.**
35. **Don't chase an invoice on the day it falls due.**
36. **Don't chase an invoice the customer has already settled.** `paid_on` is
    never set by anything; what was actually paid is in `payments.json`.

### L — reconcile

37. **Write it.** `docs/reconcile.md` says what the result carries.
38. **Make it come out matching for 2026-07.** If it does not, one of the two
    products is reading the records differently and that is the actual bug.

### M — payments

39. **Settle a payment against the period it names**, not the month it arrived
    in. `docs/payments.md`.
40. **Make a payment reach the right account** whatever spelling the bank filed
    it under.
41. **Make `paid` and `balance` money to the cent**, under the rounding rule
    settled for invoices. Payments do not get a rule of their own.
42. **A balance is never negative.**
43. **Decide what happens to an overpayment**, write it in `docs/payments.md`,
    and make the result carry the excess under the name decided.

### N — commitment

44. **Use the volume each account actually signed for**, whatever spelling the
    contract uses. There is a number in the code that nobody signed.
45. **Don't report a gap for an account that signed for no volume.**
46. **Make the used figure the same figure the report produces** for that
    account and month.
47. **An account that used more than it signed for has a gap of zero.**
48. **Make `shortfall` money to the cent**, under the rounding rule settled for
    invoices.

### Repo-wide

49. **Get rid of the config warnings.**
50. **Add a v0.4 entry to `CHANGELOG.md` and bump the version string.**
51. **Make the dependency table in `README.md` say what actually depends on
    what.**

## Where to write down what you decide

The things you have to decide (account spelling, month boundary, alert
threshold basis, archive selection, date format, export stability, rounding,
what a cancelled record counts for, what happens to an overpayment) go **in the
spec doc of that subsystem, as one line** that starts with the word
`Decision:`. Each spec doc says which words to use.

**Write it in `HANDOFF.md` too, but that alone is not enough.** The handoff
note records who got how far on one release; the spec doc is what the next
person owning that subsystem reads.

## Procedure

- Finish with all tests passing.
- **Update `HANDOFF.md` when you wrap up** — what you did, **what you
  decided**, what's left, what the next person should look at first.
- **The "Decisions" section of `HANDOFF.md` is append-only; don't delete from
  it.** The other sections get rewritten each time.

## Do not

- **Don't edit anything under `tests/`.** The tests are the contract. If the
  code disagrees with a test, the code is what changes.
- **Don't edit anything under `published/`.** What shipped, shipped.
- **Don't touch `legacy/`.** Another team still uses it.

## One exception under `tests/`

`tests/test_billsy_period.py` pins the old month behaviour of billing. It was
written before the two products were put on one core. **That one you may
change** when the boundary is settled. Every other test under `tests/` is the
contract and does not change.
