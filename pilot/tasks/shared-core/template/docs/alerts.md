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

## One basis for the whole file

**The file mixes the two right now.** The same threshold number is compared
against a month's worth on one side and against a single record on the other,
so the two rules cannot mean the same thing, and nowhere does it say why they
diverged.

**Settle on one.** Either choice is fine; what matters is that the rules file
and this section agree afterwards. Whether to keep the `basis` key at all or
drop it is part of what you decide.

**Write it in this section as one line** that starts with the word
`Decision:`, a colon, and then either whole month or last observation.

## Month boundary

**Use whatever basis the report (subsystem B) settled on.** The alerts sit on
the report's monthly aggregation; every month this subsystem names has to be a
month the report also produced, and with the same records in it. Otherwise the
records sitting on a boundary land in one month here and another month there,
and nothing raises an error.

Which way B went is written in the "Month boundary" section of
`docs/report.md`. If the previous person decided it before leaving, it will be
in `HANDOFF.md` too.

## Not missing things, and not being noisy

Two requirements that pull against each other.

- **Don't miss anything over the threshold.** Over the threshold and silent is
  the worst outcome.
- **Don't emit more than `max_alerts_per_day` alerts.** The value is in the
  config; it is 3 by default. Beyond that people stop reading them.

**On this sample they cannot both hold.** Depending on the basis you settle
on, more accounts cross their threshold than the cap allows.

**Whichever way you go, the output has to say what happened to the rest.**
The `alerts` command emits JSON; it carries a `suppressed` count — how many
crossings were not emitted as their own alert. It is `0` when nothing was
withheld, and it is never absent. Rolling several into one and dropping the
tail are both fine; a silent drop is not.
