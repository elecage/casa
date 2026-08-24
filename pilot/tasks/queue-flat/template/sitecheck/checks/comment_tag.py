"""설정에서 comment_tag 규칙을 확인한다."""

from __future__ import annotations

def check_comment_tag(parsed: dict) -> int:
    """위반 건수를 돌려준다 (옛 등록 방식).

    
    """
    hits = 0
    for key, value in parsed.items():
        if _violates_comment_tag(key, value):
            hits += 1
    return hits


def _violates_comment_tag(key: str, value: str) -> bool:
    return key.startswith("comm") and not value.strip()
