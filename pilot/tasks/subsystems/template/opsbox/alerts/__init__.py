"""서브시스템 C — 알림 규칙. 명세는 `docs/alerts.md`.

집계(서브시스템 B)가 낸 것 위에 계정별 문턱을 걸고, 넘은 것마다 알림을 낸다.

**B가 정한 달 경계를 그대로 써야 한다.** 지금은 여기서 따로 잡고 있고 그
기준이 B와 다르다 — `evaluate.py` 머리말과 `docs/alerts.md`의 "달 경계" 절.
"""

from __future__ import annotations

from . import evaluate, rules
from .evaluate import fire, last_seen, monthly_totals
from .rules import load
