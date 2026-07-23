# jobq

Tiny config-driven job queue. Settings come from `config/defaults.ini`
and can be overridden per-process with `JOBQ_*` environment variables —
for example `JOBQ_TIMEOUT_MS=250` caps how long a job may wait before it
is dropped (`timeout_ms`, milliseconds).

See `docs/CONFIG.md` for the full settings reference and
`examples/quickstart.py` for a runnable example.

## Tests

```
python -m pytest
```
