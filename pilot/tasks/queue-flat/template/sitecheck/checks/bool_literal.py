"""설정에서 bool_literal 규칙을 확인한다."""

from __future__ import annotations

def check_bool_literal(parsed: dict) -> int:
    """위반 건수를 돌려준다 (옛 등록 방식).

    
    """
    hits = 0
    for key, value in parsed.items():
        if _violates_bool_literal(key, value):
            hits += 1
    return hits


def _violates_bool_literal(key: str, value: str) -> bool:
    return key.startswith("bool") and not value.strip()
