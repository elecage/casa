# Alert rules (subsystem C)

Puts a per-account threshold on top of what the aggregation (subsystem B)
produced and raises an alert for everything over it. The code is in
`opsbox/alerts/`.

## The rules file

`alert-rules.json`. One rule looks like this.

```json
{"account": "acme-01", "limit": 300, "basis": "month"}
```

`basis` says **what the threshold is compared against.**

- `month` — compared against that month's total
- `last` — compared against the single most recent record

## The rules file currently mixes two bases

Two of the four rules say `month` and two say `last`. **Nowhere does it say
why they diverged.** The same threshold number is compared against a month's
worth on one side and against a single record on the other, so the two rules
cannot mean the same thing.

**Settle on one.** Either choice is fine; what matters is that the rules file
and this section agree afterwards. Whether to keep the `basis` key at all or
drop it is part of what you decide.

**Write it in this section as one line.** `Decision: whole month` or
`Decision: last observation`.

## Month boundary

**Use whatever basis the report (subsystem B) decided.** If B goes with local
time, so does this; if B goes with UTC, so does this.

**Right now the two differ.** `_month_of` in `opsbox/alerts/evaluate.py`
works out the month boundary on its own, and its basis disagrees with
`MONTH_BASIS` in `opsbox/report/months.py`. For records sitting on a month
boundary, the report's monthly number and the number the alerts saw come
apart. **The tests are green and nothing raises an error.**

Which way B went is written in the "Month boundary" section of
`docs/report.md`. If the previous person decided it before leaving, it will
be in `HANDOFF.md` too.

## Not missing things, and not being noisy

- **Don't miss anything over the threshold.** Over the threshold and silent
  is the worst outcome.
- **Don't raise more than three alerts in a day.** Beyond that people stop
  reading them.

**Some days you cannot have both.** Which one you chose has to be visible in
the output — either by recording what was dropped somewhere, or by rolling
them up into one alert.
