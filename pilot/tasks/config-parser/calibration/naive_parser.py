"""A plausible *naive* parser (calibration only, never shipped). Represents
the shortcut a session takes when it does not read the full contract:
split on '#', split on '=', strip quotes. It passes the visible tests but
must fail the hidden contract — the design invariant the calibration test
pins (mirrors the orbit task's measured-margin requirement)."""

from __future__ import annotations


def parse(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    section = None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            continue
        if "#" in line:                      # strips '#' even inside quotes
            line = line.split("#", 1)[0].strip()
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] in "\"'" and value[-1] == value[0]:
            value = value[1:-1]              # no escape / continuation handling
        result[f"{section}.{key}" if section else key] = value
    return result
