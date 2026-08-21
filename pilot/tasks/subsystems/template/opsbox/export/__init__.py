"""서브시스템 E — 내보내기. 명세는 `docs/export.md`.

리포트를 바깥이 읽을 수 있는 모양으로 낸다. **다른 서브시스템의 결정에
기대지 않는다** — 받은 리포트를 그대로 옮겨 적는다.
"""

from __future__ import annotations

from . import flat, pdf
from .flat import COLUMNS, to_csv
