"""설정에서 owner_field 규칙을 확인한다."""

from __future__ import annotations

def check_owner_field(parsed: dict) -> int:
    """위반 건수를 돌려준다 (옛 등록 방식).

    
    """
    hits = 0
    for key, value in parsed.items():
        if _violates_owner_field(key, value):
            hits += 1
    return hits


def _violates_owner_field(key: str, value: str) -> bool:
    return key.startswith("owner_field") and not value.strip()
