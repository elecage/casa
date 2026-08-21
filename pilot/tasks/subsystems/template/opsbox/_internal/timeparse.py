"""패키지 안에서 쓰는 기록 시각 유틸.

원천마다 기록 시각을 적는 방식이 달라서, 어댑터가 제각기 파싱하지 않도록
여기 하나로 모아 뒀다. 새 원천을 붙일 때도 이걸 쓴다.
"""

from __future__ import annotations

import datetime
import re

# 지금까지 들어온 원천들이 쓰던 표기. 앞에서부터 순서대로 시도한다.
_LAYOUTS = (
    "%Y-%m-%dT%H:%M:%S",
    "%Y/%m/%d %H:%M:%S",
    "%d-%b-%Y %H:%M:%S",
    "%Y%m%d%H%M%S",
)


def parse_ts(text: str) -> datetime.datetime:
    """기록 시각 문자열을 datetime으로 바꾼다.

    끝에 붙은 구역 표시(``Z``, ``+09:00``)는 떼고 현지 시각으로 읽는다.
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
    raise ValueError(f"알 수 없는 기록 시각 표기: {text!r}")


_OFFSET = re.compile(r"([+-])(\d{2}):(\d{2})$")


def to_utc(text: str) -> datetime.datetime:
    """구역 표시를 **살려서** 표준시로 옮긴 시각.

    `parse_ts`는 구역을 떼고 현지 시각으로 읽는다. 달 경계에 걸친 기록을
    표준시 기준으로 세려면 이쪽을 쓴다.
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
