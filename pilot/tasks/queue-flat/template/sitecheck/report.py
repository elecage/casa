"""보고서 출력."""

from __future__ import annotations

from .severity import SEVERITY


def render(results: dict) -> str:
    """검사 이름과 위반 수를 줄마다 낸다."""
    lines = []
    for name in sorted(results):
        found = results[name]
        count = found if isinstance(found, int) else len(found)
        lines.append(f"{name}\t{SEVERITY.get(name, 'warn')}\t{count}")
    return "\n".join(lines)
