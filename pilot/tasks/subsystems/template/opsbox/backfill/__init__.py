"""서브시스템 F — 되채우기. 명세는 `docs/backfill.md`.

이미 바깥으로 나간 달별 숫자(`published/`)와 지금 표본으로 다시 센 숫자를
견주어 차이를 적는다. 나간 파일은 고치지 않는다.

**둘에 기댄다.** 계정 이름은 입력 어댑터(A)가 정한 규칙을, 달 경계는
집계(B)가 정한 기준을 써야 한다. 지금은 둘 다 여기서 따로 잡고 있다.
"""

from __future__ import annotations

from . import plan
from .plan import delta, published, recomputed
