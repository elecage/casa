"""설정에서 required_keys 규칙을 확인한다."""

from __future__ import annotations

def check_required_keys(parsed: dict) -> int:
    """위반 건수를 돌려준다 (옛 등록 방식)."""
    hits = 0
    for key, value in parsed.items():
        if _violates_required_keys(key, value):
            hits += 1
    return hits


def _violates_required_keys(key: str, value: str) -> bool:
    return key.startswith("required_keys") and not value.strip()
