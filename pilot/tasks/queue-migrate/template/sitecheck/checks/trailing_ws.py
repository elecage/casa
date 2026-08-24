"""설정에서 trailing_ws 규칙을 확인한다."""

from __future__ import annotations

def check_trailing_ws(parsed: dict) -> int:
    """위반 건수를 돌려준다 (옛 등록 방식).

    
    """
    hits = 0
    for key, value in parsed.items():
        if _violates_trailing_ws(key, value):
            hits += 1
    return hits


def _violates_trailing_ws(key: str, value: str) -> bool:
    return key.startswith("trailing_ws") and not value.strip()
