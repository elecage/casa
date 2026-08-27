"""설정에서 known_hosts 규칙을 확인한다."""

from __future__ import annotations

def check_known_hosts(parsed: dict) -> int:
    """위반 건수를 돌려준다 (옛 등록 방식)."""
    hits = 0
    for key, value in parsed.items():
        if _violates_known_hosts(key, value):
            hits += 1
    return hits


def _violates_known_hosts(key: str, value: str) -> bool:
    return key.startswith("known_hosts") and not value.strip()
