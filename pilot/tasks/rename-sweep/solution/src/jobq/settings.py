"""Central configuration.

Setting keys live in SETTINGS_KEYS; values come from config/defaults.ini,
optionally overridden per-process (see env.py). Duration keys end in
``_ms`` and are always integers (milliseconds).
"""

from __future__ import annotations

import configparser
from pathlib import Path

from .errors import ConfigError

SETTINGS_KEYS = ("deadline_ms", "max_retries", "batch_size", "queue_name")

# Keys parsed as integers: durations plus counters.
_DURATION_KEYS = tuple(prefix + "_ms" for prefix in ("deadline",))
_COUNT_KEYS = ("max_retries", "batch_size")

DEFAULT_INI = Path(__file__).resolve().parent.parent.parent / "config" / "defaults.ini"


class Settings:
    def __init__(self, **values):
        for key in SETTINGS_KEYS:
            if key not in values:
                raise ConfigError(f"missing setting: {key}")
            setattr(self, key, values[key])

    def validate(self) -> None:
        # Every duration must be a positive number of milliseconds.
        for suffix in ("_ms",):
            value = getattr(self, "deadline" + suffix)
            if not isinstance(value, int) or value <= 0:
                raise ConfigError(f"deadline{suffix} must be a positive int")
        if self.max_retries < 0:
            raise ConfigError("max_retries must be >= 0")
        if self.batch_size <= 0:
            raise ConfigError("batch_size must be positive")


def _coerce(key: str, raw: str):
    if key in _DURATION_KEYS or key in _COUNT_KEYS:
        return int(raw)
    return raw


def load(path: str | Path = DEFAULT_INI, overrides: dict | None = None) -> Settings:
    parser = configparser.ConfigParser()
    if not parser.read(path):
        raise ConfigError(f"cannot read config file: {path}")
    section = parser["queue"]
    values = {key: _coerce(key, section[key]) for key in SETTINGS_KEYS}
    values.update(overrides or {})
    settings = Settings(**values)
    settings.validate()
    return settings
