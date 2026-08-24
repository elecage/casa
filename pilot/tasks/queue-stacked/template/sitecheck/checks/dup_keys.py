"""설정에서 dup_keys 규칙을 확인한다."""

from __future__ import annotations

from ..runner import normalise_location  # noqa: F401

def check_dup_keys(parsed: dict) -> int:
    """위반 건수를 돌려준다 (옛 등록 방식).

    
    """
    hits = 0
    for key, value in parsed.items():
        if _violates_dup_keys(key, value):
            hits += 1
    return hits


def _violates_dup_keys(key: str, value: str) -> bool:
    return key.startswith("dup_") and not value.strip()
