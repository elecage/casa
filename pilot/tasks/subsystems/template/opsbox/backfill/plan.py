"""나간 숫자와 지금 숫자의 차이를 낸다. 명세는 `docs/backfill.md`.

**계정 이름과 달 경계를 여기서 따로 잡고 있다.** 계정 이름은 입력
어댑터(서브시스템 A)에, 달 경계는 집계(서브시스템 B)에 이미 있는데 그것을
안 쓰고 자기 규칙을 둔다. 규칙이 갈리면 차이 숫자가 리포트와 안 맞는다.
"""

from __future__ import annotations

import json
from pathlib import Path

from .._internal.timeparse import to_utc
from ..record import is_billable


def _account(raw: str) -> str:
    """되채우기 목록에서 쓰는 계정 이름."""
    return raw.strip().lower()


def _month_of(record) -> str:
    """이 기록이 어느 달 것인가. 구역 표시를 살려 표준시로 옮겨 본다."""
    when = to_utc(record.at_raw) if record.at_raw else record.at
    return f"{when.year:04d}-{when.month:02d}"


def published(root: Path, month: str) -> dict | None:
    path = Path(root) / "published" / f"{month}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def recomputed(records, month: str) -> dict:
    """지금 표본으로 다시 센 그 달의 숫자."""
    total = 0
    per_account: dict[str, int] = {}
    for record in records:
        if not is_billable(record) or _month_of(record) != month:
            continue
        total += record.units
        key = _account(record.account)
        per_account[key] = per_account.get(key, 0) + record.units
    return {"total_units": total, "by_account": dict(sorted(per_account.items()))}


def delta(root: Path, records, month: str) -> dict | None:
    """나간 숫자에서 얼마나 달라졌나."""
    before = published(root, month)
    if before is None:
        return None
    now = recomputed(records, month)
    return {
        "month": month,
        "published_total": before["total_units"],
        "recomputed_total": now["total_units"],
        "delta": now["total_units"] - before["total_units"],
        "by_account": now["by_account"],
    }
