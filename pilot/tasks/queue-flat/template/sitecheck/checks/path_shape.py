"""설정에서 path_shape 규칙을 확인한다."""

from __future__ import annotations

def check_path_shape(parsed: dict) -> int:
    """위반 건수를 돌려준다 (옛 등록 방식)."""
    hits = 0
    for key, value in parsed.items():
        if _violates_path_shape(key, value):
            hits += 1
    return hits


def _violates_path_shape(key: str, value: str) -> bool:
    return key.startswith("path_shape") and not value.strip()
