#!/usr/bin/env python3
"""PreToolUse 훅: 봉인한 옛 수집 결과를 건드리는 것을 막는다.

**왜 이 훅이 있나 (2026-08-23 유저 지시).** 유저 원문 — "지금까지의 수집
결과들은 레거시로 별도 보관하고. 자꾸 네가 건드리면서 오래된 자료만 뒤지게
하면 안돼."

2026-08-23 세션이 하루에 여섯 번 같은 일을 되풀이했다. 기존 자료를 불러
지표를 산출하고 두 집단을 견주고, 안 갈리면 다음 지표로 넘어갔다. 여섯 번
다 새 수집이 필요했는데 매번 "새 수집이 필요 없습니다" 라고 하고 옛 자료를
다시 뒤졌다. **문서에 적어 두는 것으로는 안 지켜진다** — `CLAUDE.md` 의
설계 원칙대로 코드로 막는다.

**무엇을 막나.** `results-legacy/` 를 가리키는 도구 호출 전부. 파일을 읽는
것도, 셸에서 훑는 것도 포함한다. `harness/gates.json` 의 `legacy.state` 가
`sealed` 인 동안만 막는다.

**막지 않는 것.** 새로 만드는 수집 결과 디렉토리(`results/`)는 이 훅과 무관
하다. 옛 자료를 꼭 봐야 하면 유저에게 확인하고 `legacy.state` 를 바꾼다 —
`collection` 잠금과 같은 방식이다.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gates import load_gates  # noqa: E402

#: 봉인한 디렉토리 이름. 늘어나면 여기에 더한다.
SEALED_DIRS = ("results-legacy",)


def mentions_sealed(tool_input: dict) -> str | None:
    """그 호출이 봉인한 디렉토리를 가리키는가. 가리키면 그 이름을 준다.

    도구 인자의 **모든 문자열 값**을 본다. 경로 인자만 보면 셸 명령이
    빠져나간다.
    """
    for value in _strings(tool_input):
        text = value.replace("\\", "/")
        for name in SEALED_DIRS:
            if name in text:
                return name
    return None


def _strings(value) -> list[str]:
    """중첩된 구조 안의 문자열을 전부 모은다."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _strings(v)]
    if isinstance(value, (list, tuple)):
        return [s for v in value for s in _strings(v)]
    return []


def block_message(name: str, entry: dict) -> str:
    reason = entry.get("reason", "(사유 미기록)")
    unseal = entry.get("unseal_requires", "(해제 조건 미기록)")
    return (
        f"차단됨 — 옛 수집 결과 봉인 (harness/gates.json: legacy=sealed).\n"
        f"가리킨 곳: {name}/\n"
        f"이유: {reason}\n"
        f"해제 조건: {unseal}\n"
        "지금 할 일은 옛 자료를 다시 뒤지는 것이 아니라, 관측 대상 셋"
        "(회피·동일한 작업의 반복·문맥 이해도 저하)을 잴 수 있는 과제와 수집 "
        "환경을 설계하는 것이다. 봉인을 임의로 풀지 말고 유저에게 확인할 것."
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0  # 입력을 못 읽으면 이 훅은 판단하지 않는다.
    if not isinstance(payload, dict):
        return 0

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0

    name = mentions_sealed(tool_input)
    if name is None:
        return 0

    # 봉인한 곳을 가리키는 호출로 판정된 경우에만 잠금을 본다. 여기서 오류가
    # 나면 통과시키지 않고 막는다 — 봉인이 조용히 무력화되면 안 된다.
    entry = load_gates().get("legacy")
    if not isinstance(entry, dict):
        sys.stderr.write(
            "차단됨 — harness/gates.json의 legacy 항목을 읽지 못했다. "
            "봉인 상태를 확인할 수 없으므로 막는다.\n")
        return 2
    if entry.get("state") != "sealed":
        return 0
    sys.stderr.write(block_message(name, entry) + "\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
