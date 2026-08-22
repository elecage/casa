"""Record-timestamp helpers used inside the package.

Every source writes its record timestamps differently, so this is collected in
one place rather than parsed separately by each adapter. A new source uses
this too.
"""

from __future__ import annotations

import datetime
import re

# The layouts the sources so far have used, tried in this order.
_LAYOUTS = (
    "%Y-%m-%dT%H:%M:%S",
    "%Y/%m/%d %H:%M:%S",
    "%d-%b-%Y %H:%M:%S",
    "%Y%m%d%H%M%S",
)


def parse_ts(text: str) -> datetime.datetime:
    """Turn a record-timestamp string into a datetime.

    A trailing zone offset (``Z``, ``+09:00``) is dropped and the timestamp is
    read as local time.
    """
    raw = text.strip()
    if raw.endswith("Z"):
        raw = raw[:-1]
    elif len(raw) > 6 and raw[-6] in "+-" and raw[-3] == ":":
        raw = raw[:-6]
    for layout in _LAYOUTS:
        try:
            return datetime.datetime.strptime(raw, layout)
        except ValueError:
            continue
    raise ValueError(f"unrecognized record timestamp: {text!r}")


_OFFSET = re.compile(r"([+-])(\d{2}):(\d{2})$")


def to_utc(text: str) -> datetime.datetime:
    """The timestamp shifted to UTC, **keeping** the zone offset.

    `parse_ts` drops the offset and reads local time. Use this one to count a
    record sitting on a month boundary on a UTC basis.
    """
    raw = text.strip()
    if raw.endswith("Z"):
        return parse_ts(raw)
    found = _OFFSET.search(raw)
    if not found:
        return parse_ts(raw)
    sign, hours, minutes = found.group(1), int(found.group(2)), int(found.group(3))
    shift = datetime.timedelta(hours=hours, minutes=minutes)
    local = parse_ts(raw)
    return local - shift if sign == "+" else local + shift
