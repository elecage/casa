"""Report rendering: WindowStats -> plain dict / text."""

from __future__ import annotations

from .models import WindowStats


def build(stats: list[WindowStats]) -> dict:
    return {
        "windows": [
            {
                "start": s.start.isoformat(),
                "count": s.count,
                "errors": s.errors,
                "bytes": s.bytes_total,
            }
            for s in stats
        ],
        "totals": {
            "records": sum(s.count for s in stats),
            "errors": sum(s.errors for s in stats),
            "bytes": sum(s.bytes_total for s in stats),
        },
    }


def render_text(result: dict) -> str:
    lines = [f"{w['start']}  n={w['count']}  err={w['errors']}  bytes={w['bytes']}"
             for w in result["windows"]]
    t = result["totals"]
    lines.append(f"TOTAL  n={t['records']}  err={t['errors']}  bytes={t['bytes']}")
    return "\n".join(lines)
