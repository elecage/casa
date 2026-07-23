# Settings reference

All settings live in the `[queue]` section of `config/defaults.ini` and
can be overridden with `JOBQ_<KEY>` environment variables (key upper-cased).

| key | type | meaning |
|---|---|---|
| `deadline_ms` | int | how long a job may wait before being dropped (ms) |
| `max_retries` | int | retry attempts per failing job |
| `batch_size` | int | jobs pulled per worker cycle |
| `queue_name` | str | logical queue identifier |

Duration settings end in `_ms` and are always integers. `deadline_ms`
must be positive; see `Settings.validate()`.
