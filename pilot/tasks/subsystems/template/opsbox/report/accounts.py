"""계정별 합계.

계정 이름은 어댑터가 이미 맞춰 놓은 것을 그대로 쓴다
(`opsbox.ingest.accounts.normalize_account`). **여기서 다시 맞추지 않는다** —
규칙이 두 군데로 갈라지면 한쪽이 못 맞춘 계정이 조용히 두 줄로 남는다.
"""

from __future__ import annotations

from ..record import is_billable


def by_account(records) -> dict[str, int]:
    out: dict[str, int] = {}
    for record in records:
        if is_billable(record):
            out[record.account] = out.get(record.account, 0) + record.units
    return dict(sorted(out.items()))
