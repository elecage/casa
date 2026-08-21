"""설정 읽기.

설정 파일이 없거나 열쇠가 빠져 있으면 **경고만 찍고 기본값으로 돈다.**
멈추지 않는 것은 일부러다 — 야간 작업이 설정 하나 때문에 통째로 죽는 것보다
낫다고 보고 그렇게 뒀다.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

CONFIG_NAME = "config.sample.json"

DEFAULTS = {
    "data_dir": "data",
    "as_of": "2026-10-15",     # 보관 판정의 기준일
    "retain_days": 90,
    "max_alerts_per_day": 3,
}


def load(root: Path) -> dict:
    path = Path(root) / CONFIG_NAME
    out = dict(DEFAULTS)
    if not path.is_file():
        print(f"경고: {CONFIG_NAME} 이 없다. 기본값으로 돈다.", file=sys.stderr)
        return out
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        print(f"경고: {CONFIG_NAME} 을 못 읽었다. 기본값으로 돈다.", file=sys.stderr)
        return out
    for key, value in raw.items():
        if key not in DEFAULTS:
            print(f"경고: 모르는 설정 열쇠 {key!r} — 무시한다.", file=sys.stderr)
            continue
        out[key] = value
    return out
