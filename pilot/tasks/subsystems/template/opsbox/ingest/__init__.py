"""서브시스템 A — 입력 어댑터. 명세는 `docs/ingest.md`.

원천마다 파일 형식이 다르다. 어댑터는 그 형식을 읽어 `opsbox.record.Record`
목록으로 내놓는 일만 한다. 집계도 정렬도 여기서 하지 않는다.

**계정 표기는 원천마다 다르다.** 같은 계정이 원천에 따라 대소문자와 앞뒤
공백이 다르게 적혀 온다. 어떻게 맞출지는 `docs/ingest.md`의 "계정 표기" 절.
"""

from __future__ import annotations

from pathlib import Path

from . import ac, bd, cj, df, eg, fh
from .accounts import normalize_account

#: 붙어 있는 어댑터들. 새 원천을 붙이면 여기에 등록한다.
ADAPTERS = {
    "ac": ac,
    "bd": bd,
    "cj": cj,
    "df": df,
    "eg": eg,
    "fh": fh,
}


def read_all(data_dir: Path) -> list:
    """`data/` 아래에서 붙어 있는 어댑터가 읽을 수 있는 것을 전부 읽는다."""
    out = []
    for name, adapter in sorted(ADAPTERS.items()):
        for path in sorted(Path(data_dir).glob(adapter.PATTERN)):
            out.extend(adapter.read(path))
    return out
