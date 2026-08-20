"""원천별 입력 어댑터.

새 원천이 늘 때마다 여기 모듈을 하나 더하고 ``REGISTRY``에 등록한다.
어댑터는 파일 하나를 받아 ``Record`` 목록을 돌려주기만 하면 된다.
"""

from __future__ import annotations

from pathlib import Path

from . import scs, sfw, sjs, sjl, sth

REGISTRY = {
    "scs": scs,
    "sfw": sfw,
    "sjl": sjl,
    "sth": sth,
    "sjs": sjs,
}


def read_all(source_dir: str | Path) -> list:
    """원천 디렉토리 아래 파일을 등록된 어댑터로 전부 읽는다."""
    records = []
    for name, module in sorted(REGISTRY.items()):
        for path in sorted(Path(source_dir).glob(module.PATTERN)):
            records.extend(module.read(path))
    return records
