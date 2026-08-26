"""설정에서 list_order 규칙을 확인한다."""

from __future__ import annotations

def check_list_order(parsed: dict) -> int:
    """위반 건수를 돌려준다 (옛 등록 방식).

    
    """
    hits = 0
    for key, value in parsed.items():
        if _violates_list_order(key, value):
            hits += 1
    return hits


def _violates_list_order(key: str, value: str) -> bool:
    return key.startswith("list_order") and not value.strip()
