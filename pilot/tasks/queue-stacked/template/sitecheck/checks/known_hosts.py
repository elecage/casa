"""설정에서 known_hosts 규칙을 확인한다."""

from __future__ import annotations

def check_known_hosts(parsed: dict) -> int:
    """위반 건수를 돌려준다 (옛 등록 방식).

    허용 목록이 필요하다. fixtures/known-hosts.txt 참조.
    
    """
    hits = 0
    for key, value in parsed.items():
        if _violates_known_hosts(key, value):
            hits += 1
    return hits


def _violates_known_hosts(key: str, value: str) -> bool:
    from pathlib import Path
    allowed = Path("fixtures/known-hosts.txt")
    if not allowed.is_file():
        return False
    known = allowed.read_text(encoding='utf-8').split()
    return value not in known
