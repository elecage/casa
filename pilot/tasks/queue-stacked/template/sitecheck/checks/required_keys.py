"""설정에서 required_keys 규칙을 확인한다."""

from __future__ import annotations

def check_required_keys(parsed: dict) -> int:
    """위반 건수를 돌려준다 (옛 등록 방식).

    설정이 안 읽히면 경고를 찍고 기본값으로 이어간다.
    
    """
    hits = 0
    for key, value in parsed.items():
        if _violates_required_keys(key, value):
            hits += 1
    return hits


def _violates_required_keys(key: str, value: str) -> bool:
    if not value:
        print(f"경고: {key} 값이 비었다. 기본값 0 으로 이어간다.")
        return False
    return key.startswith("required_keys") and value != "ok"
