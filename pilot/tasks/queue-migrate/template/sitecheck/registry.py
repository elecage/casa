"""새 등록 방식. 검사는 여기에 등록한다."""

from __future__ import annotations

CHECKS: dict[str, object] = {}


def register(name: str):
    """검사를 새 등록부에 넣는다."""
    def wrap(func):
        CHECKS[name] = func
        return func
    return wrap


@register("indent")
def indent(parsed: dict) -> list[dict]:
    """위반 목록을 돌려준다."""
    return [{'key': k, 'rule': 'indent'}
            for k, v in parsed.items()
            if k.startswith("indent") and not v.strip()]


@register("schema_version")
def schema_version(parsed: dict) -> list[dict]:
    """위반 목록을 돌려준다."""
    return [{'key': k, 'rule': 'schema_version'}
            for k, v in parsed.items()
            if k.startswith("schema_version") and not v.strip()]

