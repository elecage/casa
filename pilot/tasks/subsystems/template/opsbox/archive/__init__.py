"""서브시스템 D — 보관과 정리. 명세는 `docs/archive.md`.

오래됐거나 큰 것을 골라 보관 목록을 만든다.

**입력 어댑터(서브시스템 A)가 정한 계정 표기 규칙을 그대로 써야 한다.**
지금은 `select.py`가 자기 규칙을 따로 두고 있어서 두 쪽 이름이 어긋난다.
"""

from __future__ import annotations

from . import manifest, select
from .manifest import render
from .select import by_age, by_size, older_than
