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
def indent(parsed: dict) -> int:
    """위반 건수를 돌려준다. 옛 방식 그대로 옮겨 두었다."""
    return sum(1 for k, v in parsed.items()
               if k.startswith("indent") and not v.strip())


@register("null_value")
def null_value(parsed: dict) -> int:
    """위반 건수를 돌려준다. 옛 방식 그대로 옮겨 두었다."""
    return sum(1 for k, v in parsed.items()
               if k.startswith("null_value") and not v.strip())


@register("schema_version")
def schema_version(parsed: dict) -> int:
    """위반 건수를 돌려준다. 옛 방식 그대로 옮겨 두었다."""
    return sum(1 for k, v in parsed.items()
               if k.startswith("schema_version") and not v.strip())

