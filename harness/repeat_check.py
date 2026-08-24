#!/usr/bin/env python3
"""Stop 훅: 기존 자료로 같은 분석을 되풀이하고 끝내려 하면 한 번 되돌려보낸다.

**왜 이 훅이 있나 (2026-08-24 유저 지시).** 유저 물음 — "이걸 네가 나인 것처럼
모사하는 훅을 만들 수 있냐는거야."

유저가 하는 지적 중 **둘째 종류**를 담당한다 — 기록된 상태와 어긋난 것.
유저가 이것을 알아채는 이유는 유저가 세션이 무엇을 몇 번 했는지 기억하기
때문이고, 그 기록은 트랜스크립트와 `harness/gates.json` 에 있다. 첫째 종류인
글로 적힌 규칙 위반은 `wording_check.py` 가 담당하고, 셋째 종류인 설계의
모순은 결정론으로 판정되지 않는다.

**무엇을 보나.** 2026-08-23 세션이 하루에 여섯 번 같은 절차를 되풀이했다 —
기존 자료를 불러 지표를 산출하고 두 집단을 대조하고, 값이 서로 다르지 않으면
다음 지표로 넘어갔다. 여섯 번 다 예측을 봉인하지 않은 사후 탐색이었고
아무것도 닫지 못했다. **매번 세부 호출이 달라서 기존 지표
(`action_cycle_length`, `max_repetition`)에 검출되지 않았다.**

그래서 호출 하나하나가 아니라 **분석 스크립트를 몇 번 실행했는가**를 센다.
검출 조건 둘 중 하나면 차단한다.

1. `pilot/analysis/` 아래 스크립트를 통틀어 `total` 회 이상 실행했다.
2. 한 스크립트를 서로 다른 인자로 `variants` 회 이상 실행했다.

**수집 잠금이 걸려 있을 때만 본다.** 잠금이 열려 있으면 새 자료를 모으는
중이고, 그때 분석을 여러 번 실행하는 것은 정상이다. 이 훅이 검출하려는 것은
**새 수집 없이 옛 자료만 다시 산출하는 것**이다.

**세션당 한 번만** 차단한다. 계약: stdin JSON의 `transcript_path` 가 이 세션의
기록이고, exit 2면 종료를 막고 stderr 가 모델에 전달된다.
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gates import REPO, gate_state, load_gates  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

#: 분석 스크립트가 사는 곳. 늘어나면 여기에 더한다.
ANALYSIS_DIRS = ("pilot/analysis/",)

#: 실행 하나에서 스크립트 경로를 뽑는 표현. `-m` 으로 부르는 형태는 경로가
#: 아니라 모듈 이름이라 따로 본다.
_SCRIPT = re.compile(r"(?:^|[\s'\"])((?:[\w./\\-]*/)?pilot[/\\]analysis[/\\][\w-]+\.py)")

DEFAULT_TOTAL = 8
DEFAULT_VARIANTS = 4


def read_calls(transcript: Path) -> list[dict]:
    """기록에서 도구 호출만 뽑는다. 파서는 관용적이어야 한다 — 모르는 줄에서
    죽으면 훅이 세션을 막는다."""
    calls: list[dict] = []
    try:
        lines = transcript.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return calls
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        message = row.get("message") if isinstance(row, dict) else None
        content = (message or {}).get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            continue
        for item in content:
            if isinstance(item, dict) and item.get("type") == "tool_use":
                calls.append({"name": item.get("name"),
                              "input": item.get("input")})
    return calls


def analysis_runs(calls: list[dict]) -> list[tuple[str, str]]:
    """분석 스크립트 실행들. 스크립트 이름과 그 뒤 인자 문자열의 쌍이다."""
    runs: list[tuple[str, str]] = []
    for call in calls:
        payload = call.get("input") or {}
        command = payload.get("command")
        if not isinstance(command, str):
            continue
        text = command.replace("\\", "/")
        for match in _SCRIPT.finditer(text):
            path = match.group(1)
            name = path.rsplit("/", 1)[-1]
            args = text[match.end():]
            # 한 셸 명령에 여러 실행이 이어져 있으면 그 자리에서 끊는다.
            args = re.split(r"[;&|]|\n", args)[0].strip()
            runs.append((name, args))
    return runs


def group_runs(runs: list[tuple[str, str]]) -> dict[str, set[str]]:
    """스크립트마다 서로 다른 인자 묶음."""
    grouped: dict[str, set[str]] = defaultdict(set)
    for name, args in runs:
        grouped[name].add(args)
    return dict(grouped)


def judge(runs: list[tuple[str, str]], total: int = DEFAULT_TOTAL,
          variants: int = DEFAULT_VARIANTS) -> dict | None:
    """차단할 것인가. 차단하면 무엇이 걸렸는지 담아 준다."""
    grouped = group_runs(runs)
    repeated = {name: sorted(args) for name, args in grouped.items()
                if len(args) >= variants}
    if len(runs) >= total or repeated:
        return {"total": len(runs), "scripts": sorted(grouped),
                "repeated": repeated}
    return None


def build_message(found: dict, entry: dict) -> str:
    lines = [
        "되풀이 검사 — 이 세션은 새 수집 없이 기존 자료로 분석을 "
        f"{found['total']}회 실행하고 끝내려 한다.",
        f"실행한 스크립트: {', '.join(found['scripts'])}",
    ]
    for name, args in found["repeated"].items():
        lines.append(f"  {name} 을 서로 다른 인자로 {len(args)}회 실행했다")
    lines.append(
        "2026-08-23 세션이 같은 절차를 여섯 번 되풀이했고 여섯 번 다 예측을 "
        "봉인하지 않은 사후 탐색이었다. 하루에 닫은 질문이 없다."
    )
    lines.append(
        "끝내기 전에 셋 중 하나를 할 것. (1) 무엇을 예측했고 그 예측을 어느 "
        "파일에 언제 적었는지 밝힌다. (2) 새 수집이 필요하면 유저에게 잠금 "
        "해제 승인을 요청한다 — "
        f"{entry.get('unlock_requires', 'harness/gates.json 의 unlock_requires')}. "
        "(3) 이 분석이 되풀이가 아닌 이유를 STATUS.md 에 적는다."
    )
    lines.append("이 검사는 세션당 한 번만 뜬다.")
    return "\n".join(lines)


def _marker(session_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", session_id or "unknown")[:80]
    return REPO / ".casa" / "harness" / f"repeat_check_{safe}.marker"


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    if not isinstance(payload, dict):
        return 0
    if payload.get("stop_hook_active"):
        return 0

    gates = load_gates()
    entry = gates.get("repeat_check")
    entry = entry if isinstance(entry, dict) else {}
    if entry.get("state", "on") != "on":
        return 0

    # 잠금이 열려 있으면 새 자료를 모으는 중이다. 그때는 보지 않는다.
    if gate_state("collection") != "locked":
        return 0

    transcript = payload.get("transcript_path")
    if not isinstance(transcript, str) or not transcript:
        return 0

    total = entry.get("total", DEFAULT_TOTAL)
    variants = entry.get("variants", DEFAULT_VARIANTS)
    total = total if isinstance(total, int) and total > 0 else DEFAULT_TOTAL
    variants = variants if isinstance(variants, int) and variants > 0 else DEFAULT_VARIANTS

    found = judge(analysis_runs(read_calls(Path(transcript))), total, variants)
    if found is None:
        return 0

    marker = _marker(str(payload.get("session_id", "")))
    if marker.exists():
        return 0
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("blocked once\n", encoding="utf-8")
    except OSError:
        pass

    collection = gates.get("collection")
    collection = collection if isinstance(collection, dict) else {}
    sys.stderr.write(build_message(found, collection) + "\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
