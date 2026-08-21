"""리포트를 줄 단위 표로 내보낸다. 모양은 `docs/export.md`."""

from __future__ import annotations

import datetime

#: 내보내는 열 순서. `docs/export.md` 와 같아야 한다.
COLUMNS = ("account", "month", "units")


def rows(report: dict) -> list[tuple]:
    out = []
    for account, units in sorted(report["by_account"].items()):
        out.append((account, "", units))
    return out


def to_csv(report: dict) -> str:
    """쉼표로 구분한 표.

    첫 줄에 만든 시각을 적는다. 언제 뽑은 것인지 알 수 있게.
    """
    stamp = datetime.datetime.now().isoformat(timespec="seconds")
    lines = [f"# generated {stamp}", ",".join(COLUMNS)]
    for row in rows(report):
        lines.append(",".join(str(value) for value in row))
    return "\n".join(lines) + "\n"
