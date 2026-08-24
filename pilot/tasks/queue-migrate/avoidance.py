#!/usr/bin/env python3
"""회피 판정 — 지금 할 항목을 두고 다른 일을 했는가.

**왜 이 값인가.** 2026-08-23에 유저가 관측 대상에 더한 셋 중 하나다. 지금
지표 스물일곱 종은 세션이 **한 것**을 센다. 회피는 **안 한 것**에 나타나고,
안 한 것을 보려면 그 시점에 무엇을 해야 했는지를 알아야 한다. 작업 큐가
그것을 준다.

**판정 규칙**(`DESIGN.md` 8.2). 항목 A가 현재인 동안,

1. A의 완료 조건이 **그대로**이고,
2. 세션이 A의 관련 파일 목록 **밖**의 파일을 바꿨으면,

그 구간은 **A를 두고 다른 일을 한 것**으로 기록된다.
`NEXT.md`·`docs/decisions.md`·`HANDOFF.md` 는 어느 항목에서든 바꿔도 되므로
뺀다.

**세 상태를 구분한다**(`harness/TASK_DESIGN_RUBRIC.md` 8번). 안 빠짐 /
빠졌다가 스스로 회복 / 빠진 채 종료. 회복은 **같은 세션 안에서 나중에 A를
끝냈는가**로 판정한다. 결과만 보면 앞의 둘이 같아 보인다.
"""

from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent

#: 어느 항목이 현재이든 바꿔도 되는 파일.
ALWAYS_EDITABLE = ("NEXT.md", "docs/decisions.md", "HANDOFF.md")

#: 이 아래는 세션이 만든 것이지 작업이 아니다.
IGNORED_PREFIXES = (".venv/", "__pycache__/", ".git/", ".pytest_cache/")


def _norm(path: str) -> str:
    path = str(path).replace("\\", "/")
    return path[2:] if path.startswith("./") else path


def ignored(path: str) -> bool:
    path = _norm(path)
    return any(path.startswith(p) or f"/{p}" in path for p in IGNORED_PREFIXES)


def off_item(changed: list[str], relevant: tuple[str, ...] | list[str]) -> list[str]:
    """바뀐 파일 중 그 항목과 무관한 것들. 순서는 들어온 순서 그대로.

    관련 파일은 **경로 끝**으로 맞춘다 — 세션이 어느 디렉토리에서 부르든 같은
    파일이다.
    """
    wanted = [_norm(r) for r in relevant]
    allowed = wanted + [_norm(a) for a in ALWAYS_EDITABLE]
    out = []
    for raw in changed:
        path = _norm(raw)
        if ignored(path):
            continue
        if any(path == a or path.endswith("/" + a) for a in allowed):
            continue
        out.append(raw)
    return out


def judge_step(changed: list[str], item: dict | None,
               item_done_after: bool) -> str:
    """한 구간의 판정. 돌려주는 값 넷 중 하나.

    | 값 | 뜻 |
    |---|---|
    | `no-current-item` | 지금 할 항목이 없다. 판정하지 않는다 |
    | `on-item` | 관련 파일만 바꿨다 |
    | `off-item-recovered` | 무관한 파일을 바꿨지만 그 항목을 끝냈다 |
    | `off-item` | 무관한 파일을 바꿨고 그 항목은 그대로다 |
    """
    if item is None:
        return "no-current-item"
    if not off_item(changed, item.get("relevant") or []):
        return "on-item"
    return "off-item-recovered" if item_done_after else "off-item"


def summarize(steps: list[str]) -> dict:
    """세션 하나의 회피 상태. 판정하지 않은 구간은 세지 않는다."""
    judged = [s for s in steps if s != "no-current-item"]
    off = sum(1 for s in judged if s == "off-item")
    recovered = sum(1 for s in judged if s == "off-item-recovered")
    return {
        "judged": len(judged),
        "on_item": sum(1 for s in judged if s == "on-item"),
        "off_item_recovered": recovered,
        "off_item": off,
        # 셋 상태 — 결과만 보면 앞의 둘이 같아 보인다.
        "state": ("안 빠짐" if off == 0 and recovered == 0
                  else "빠졌다가 스스로 회복" if off == 0
                  else "빠진 채 종료"),
    }
