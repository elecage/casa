"""Reading the settings.

If the config file is missing or a key is absent, this **only prints a warning
and runs with the defaults.** Not stopping is deliberate — better that than
having a nightly job die whole over one setting.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

CONFIG_NAME = "config.sample.json"

DEFAULTS = {
    "data_dir": "data",
    "as_of": "2026-10-15",     # reference date for archive decisions
    "retain_days": 90,
    "max_alerts_per_day": 3,
}


def load(root: Path) -> dict:
    path = Path(root) / CONFIG_NAME
    out = dict(DEFAULTS)
    if not path.is_file():
        print(f"warning: no {CONFIG_NAME}; running with defaults.",
              file=sys.stderr)
        return out
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        print(f"warning: could not read {CONFIG_NAME}; running with defaults.",
              file=sys.stderr)
        return out
    for key, value in raw.items():
        if key not in DEFAULTS:
            print(f"warning: unknown config key {key!r} — ignoring it.",
                  file=sys.stderr)
            continue
        out[key] = value
    return out
