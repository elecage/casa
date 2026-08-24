"""설정에서 line_length 규칙을 확인한다."""

from __future__ import annotations

def check_line_length(parsed: dict) -> int:
    """위반 건수를 돌려준다 (옛 등록 방식).

    폭 계산에 문자 폭 문제가 있다 — docs/checks 참조.
    
    """
    hits = 0
    for key, value in parsed.items():
        if _violates_line_length(key, value):
            hits += 1
    return hits


def _violates_line_length(key: str, value: str) -> bool:
    return key.startswith("line") and not value.strip()
