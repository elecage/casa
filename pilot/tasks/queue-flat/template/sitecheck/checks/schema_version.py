"""설정에서 schema_version 규칙을 확인한다."""

from __future__ import annotations

def check_schema_version(parsed: dict) -> int:
    """위반 건수를 돌려준다 (옛 등록 방식)."""
    hits = 0
    for key, value in parsed.items():
        if _violates_schema_version(key, value):
            hits += 1
    return hits


def _violates_schema_version(key: str, value: str) -> bool:
    return key.startswith("schema_version") and not value.strip()
