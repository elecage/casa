"""Per-process overrides: JOBQ_<KEY> environment variables.

String values are coerced exactly like the config file: integer keys
(durations and counters) become int, everything else stays str.
"""

from __future__ import annotations

import os

from .settings import SETTINGS_KEYS, _coerce


def overrides(environ: dict[str, str] | None = None) -> dict:
    environ = os.environ if environ is None else environ
    out = {}
    for key in SETTINGS_KEYS:
        env_name = "JOBQ_" + key.upper()
        if env_name in environ:
            out[key] = _coerce(key, environ[env_name])
    return out
