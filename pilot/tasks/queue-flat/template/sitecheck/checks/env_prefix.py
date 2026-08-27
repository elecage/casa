"""설정에서 env_prefix 규칙을 확인한다."""

from __future__ import annotations

def check_env_prefix(parsed: dict) -> int:
    """위반 건수를 돌려준다 (옛 등록 방식)."""
    hits = 0
    for key, value in parsed.items():
        if _violates_env_prefix(key, value):
            hits += 1
    return hits


def _violates_env_prefix(key: str, value: str) -> bool:
    return key.startswith("env_prefix") and not value.strip()
