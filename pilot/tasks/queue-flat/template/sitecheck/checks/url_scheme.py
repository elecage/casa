"""설정에서 url_scheme 규칙을 확인한다."""

from __future__ import annotations

def check_url_scheme(parsed: dict) -> int:
    """위반 건수를 돌려준다 (옛 등록 방식).

    
    """
    hits = 0
    for key, value in parsed.items():
        if _violates_url_scheme(key, value):
            hits += 1
    return hits


def _violates_url_scheme(key: str, value: str) -> bool:
    return key.startswith("url_") and not value.strip()
