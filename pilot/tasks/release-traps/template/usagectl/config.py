"""설정 파일 로더."""

from __future__ import annotations

import json
import sys
from pathlib import Path

DEFAULT_SOURCE_DIR = "data"
DEFAULT_MAX_ROWS = 750


def load(path: str | Path) -> dict:
    """설정을 읽는다. 없는 항목은 기본값으로 채운다."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    settings = {
        "source_dir": raw.get("source_dir", DEFAULT_SOURCE_DIR),
        "max_rows": raw.get("max_rows", DEFAULT_MAX_ROWS),
    }
    if "source_dir" not in raw:
        print(
            f"경고: 설정에 source_dir가 없어 기본 경로 {DEFAULT_SOURCE_DIR!r}를 쓴다.",
            file=sys.stderr,
        )
    return settings
