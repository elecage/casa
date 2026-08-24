"""설정에서 path_shape 규칙을 확인한다."""

from __future__ import annotations

def normalise_location(raw: str) -> str:
    """경로 표기를 하나로 맞춘다. 슬래시와 끝의 구분자를 정리한다."""
    return raw.replace("\\", "/").rstrip("/").strip()

def check_path_shape(parsed: dict) -> int:
    """위반 건수를 돌려준다 (옛 등록 방식).

    
    """
    hits = 0
    for key, value in parsed.items():
        if _violates_path_shape(key, value):
            hits += 1
    return hits


def _violates_path_shape(key: str, value: str) -> bool:
    return key.startswith("path") and not value.strip()
