"""설정에서 null_value 규칙을 확인한다."""

from __future__ import annotations

def check_null_value(parsed: dict) -> int:
    """위반 건수를 돌려준다 (옛 등록 방식).

    
    """
    hits = 0
    for key, value in parsed.items():
        if _violates_null_value(key, value):
            hits += 1
    return hits


def _violates_null_value(key: str, value: str) -> bool:
    return key.startswith("null_value") and not value.strip()
