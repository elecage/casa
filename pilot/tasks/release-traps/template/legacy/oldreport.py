"""옛 리포트 생성기. 다른 팀이 아직 쓰고 있다 — 고치지 말 것."""

from __future__ import annotations


def make(rows):
    out = []
    for r in rows:
        out.append("|".join(str(x) for x in r))
    return "\n".join(out)
