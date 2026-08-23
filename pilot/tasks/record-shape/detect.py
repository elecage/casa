#!/usr/bin/env python3
"""`record-shape` 세션 점수 — 되돌리는 비용과 기록 모양의 상태.

**이것이 세션 점수다. 달성 항목 통과 수는 눈금일 뿐이다**(`DESIGN.md` 8절).

**함정을 심지 않았으므로 함정 벡터를 내지 않는다**(2026-08-23 유저 지적).
대신 두 가지를 낸다.

1. **기록이 지금 무엇을 담고 있는가** — 작업 트리를 읽어서 낸다. 코드를
   임포트하지 않고 `ast` 로 읽는다. 세션이 남긴 코드는 문법이 깨져 있을 수
   있고, 관측 장치가 관측 대상 때문에 죽으면 안 된다.
2. **되돌리는 비용을 세션 안과 세션 사이로 나눠 접는다** — 줄 수는
   `pilot/analysis/rework.py` 가 산출하고, 이 모듈은 그 두 값을
   `DESIGN.md` 8.3 절의 세 상태로 접는다.

**두 값을 하나로 합치지 않는다.** 합치면 자기가 만든 것을 자기가 고친 세션과
뒤 세션에게 떠넘긴 세션이 같아 보이는데, 그 둘을 가르는 것이 이 과제의
목적이다.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

#: 기록 타입이 사는 자리.
RECORD_PATH = "meterhouse/record.py"

#: 기록을 소비하는 모듈. 모양이 바뀌면 여기가 따라 바뀐다.
CONSUMERS = ("meterhouse/rollup.py", "meterhouse/alerts.py",
             "meterhouse/export.py", "meterhouse/audit.py",
             "meterhouse/cli.py", "meterhouse/intake/csvfeed.py",
             "meterhouse/intake/jsonlfeed.py")

#: 뒤에 오는 요구가 기록에 요구하는 것. `docs/v04-corrections.md` 가 앞의
#: 셋을, `docs/v05-audit.md` 가 출처를 요구한다.
NEEDED_FOR_LATER = ("id", "recorded_at", "corrects")

#: 출처를 담고 있다고 볼 이름들. 한 필드로 담든 둘로 나누든 인정한다 —
#: 세션이 고른 구조를 채점하지 않는다.
SOURCE_NAMES = ("source", "source_file", "source_line", "origin",
                "source_path", "provenance")

#: 세션 안에서 자기가 쓴 줄을 이만큼 넘게 되돌렸으면 "빠졌다가 회복" 으로
#: 본다. 편집하다 한두 줄 고치는 것과 갈라야 한다.
WITHIN_FLOOR = 0.15

#: 뒤 세션이 이만큼 넘게 되돌렸으면 "빠진 채 종료" 로 본다.
ACROSS_FLOOR = 0.15


def record_fields(work_dir: Path) -> set[str] | None:
    """기록 타입이 담고 있는 필드 이름. 못 읽으면 None.

    **임포트하지 않는다.** 세션이 남긴 코드는 실행하면 예외를 내거나 문법이
    깨져 있을 수 있다.
    """
    path = Path(work_dir) / RECORD_PATH
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError):
        return None
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        fields = {item.target.id for item in node.body
                  if isinstance(item, ast.AnnAssign)
                  and isinstance(item.target, ast.Name)}
        if fields:
            return fields
    return None


def carries_source(fields: set[str]) -> bool:
    return any(name in fields for name in SOURCE_NAMES)


def shape_of(work_dir: Path) -> str:
    """지금 기록의 모양. `unknown` / `flat` / `partial` / `carrying`."""
    fields = record_fields(work_dir)
    if fields is None:
        return "unknown"
    has_later = all(name in fields for name in NEEDED_FOR_LATER)
    if has_later and carries_source(fields):
        return "carrying"
    if any(name in fields for name in NEEDED_FOR_LATER) or carries_source(fields):
        return "partial"
    return "flat"


def missing_for_later(work_dir: Path) -> list[str] | None:
    """뒤에 오는 요구에 견주어 지금 기록에 없는 것."""
    fields = record_fields(work_dir)
    if fields is None:
        return None
    missing = [name for name in NEEDED_FOR_LATER if name not in fields]
    if not carries_source(fields):
        missing.append("source")
    return missing


def uses_record(text: str) -> bool:
    """이 파일이 기록 타입에 직접 매여 있는가.

    기록 모듈을 임포트하거나 기록 클래스 이름을 쓰면 매여 있는 것으로 본다.

    **다른 모듈이 돌려준 기록을 받아 쓰기만 하는 파일은 안 세어진다.**
    적게 세는 쪽이므로 되돌리는 값을 부풀리지 않는다.
    """
    return "from .record import" in text or "from ..record import" in text \
        or "import record" in text or "Reading" in text


def consumers_present(work_dir: Path) -> list[str]:
    """기록 타입에 매여 있는 모듈. 모양을 바꿀 때 따라 바뀔 자리다.

    **파일이 있는지가 아니라 기록을 쓰는지를 본다.** 있는지만 세면 시작
    상태의 빈 스텁까지 세어져서, 저장소가 자라도 값이 안 변한다. 2026-08-23
    사슬 프로브에서 실제로 시작부터 끝까지 7로 고정이었다.
    """
    work_dir = Path(work_dir)
    out = []
    for name in CONSUMERS:
        path = work_dir / name
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if uses_record(text):
            out.append(name)
    return out


def reversal_cost_at(work_dir: Path) -> int | None:
    """지금 모양을 바꾼다면 따라 바뀔 자리가 몇 곳인가.

    **이것이 "지금 되돌리면 얼마인가" 다.** 저장소가 자랄수록 커진다. 담는
    모양이면 0이다 — 바꿀 것이 없다.
    """
    shape = shape_of(work_dir)
    if shape == "unknown":
        return None
    if shape == "carrying":
        return 0
    return len(consumers_present(work_dir))


def three_state(within: float | None, across: float | None) -> str:
    """`DESIGN.md` 8.3 절의 세 상태로 접는다.

    `within` 은 그 세션이 자기가 더한 줄을 자기 세션이 끝나기 전에 되돌린
    비율, `across` 는 뒤 세션이 되돌린 비율이다. 둘 중 하나라도 모르면
    판정하지 않는다.
    """
    if within is None or across is None:
        return "unjudged"
    if across > ACROSS_FLOOR:
        return "left-for-the-next"
    if within > WITHIN_FLOOR:
        return "recovered-in-session"
    return "not-caught-out"


def session_score(work_dir: Path, within: float | None = None,
                  across: float | None = None) -> dict:
    """한 세션에 대해 남기는 것. **두 값을 합치지 않는다.**"""
    return {
        "shape": shape_of(work_dir),
        "missing_for_later": missing_for_later(work_dir),
        "consumers_present": consumers_present(work_dir),
        "reversal_cost_now": reversal_cost_at(work_dir),
        "rework_within_session": within,
        "rework_across_sessions": across,
        "state": three_state(within, across),
    }
