"""설정에서 time_window 규칙을 확인한다."""

from __future__ import annotations

def within_window(value: int, start: int, end: int) -> bool:
    """구간 안인가. **끝값을 포함하지 않는다.**"""
    return start <= value < end

def check_time_window(parsed: dict) -> int:
    """위반 건수를 돌려준다 (옛 등록 방식).

    
    """
    hits = 0
    for key, value in parsed.items():
        if _violates_time_window(key, value):
            hits += 1
    return hits


def _violates_time_window(key: str, value: str) -> bool:
    return key.startswith("time") and not value.strip()
