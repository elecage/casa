#!/usr/bin/env python3
"""Stop 훅: 이미 틀린 것으로 확인된 사실 주장을 답이 되풀이하면 되돌려보낸다.

**왜 이 훅이 있나 (2026-08-26 유저 지시).** 유저 물음 — "기존의 레거시
문제들이 자꾸 튀어나오면 안돼."

실제로 있었던 일이다. `harness/anchor.md` 가 옛 과제 열한 종을 한 문장으로
잘못 적었고, 그 문장이 다른 파일 다섯으로 옮겨 적혔으며, 2026-08-26 세션이
그것을 검증 없이 유저에게 인용했다. 앵커의 문장은 그날 고쳤지만 옮겨 적힌
쪽은 남아 있었고, 유저가 다시 물어서야 드러났다. **한 자리를 고치는 것으로는
같은 문장이 다시 나오는 것을 막지 못한다.**

목록은 `harness/claim_rules.json` 이고 **유저가 지적한 사실 오류 하나가 항목
하나가 된다** — `harness/wording_rules.json` 이 말 하나에 대해 하는 것과 같다.

**항목 하나는 둘로 이루어진다.** `pattern` 은 틀린 서술이고 `scope` 는 그
서술이 무엇에 대한 것인지다. 둘이 **같은 문단**에서 다 맞아야 검출한다. 같은
표현이 다른 대상에 대해서는 맞는 말이기 때문이다 — 예를 들어 `harness/anchor.md`
의 "반복된 실수" 3번은 새로 만드는 과제가 `또 "함수 하나 구현"이면` 아무것도
바뀌지 않은 것이라고 적는데, 그것은 새 과제에 대한 규칙이지 옛 과제에 대한
서술이 아니다.

**틀린 문장을 이름으로 부를 때는 백틱으로 감싼다** — 이 검사는 인라인 코드와
코드 블록과 인용 줄을 빼고 본다. 그렇게 하지 않으면 정정하는 글 자체가
차단된다.

파일에 대해서는 `harness/check_claims.py` 가 같은 목록으로 pre-commit 에서
검사한다. 이 훅은 답에 대해서 본다 — 2026-08-26의 실제 경로가 그 둘이었다.

**세션당 한 번만** 차단한다. 계약: stdin JSON의 `last_assistant_message` 가
마지막 답, exit 2면 종료를 막고 stderr 가 모델에 전달된다.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gates import REPO, load_gates  # noqa: E402
from wording_check import strip_code  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

RULES_FILE = Path(__file__).resolve().parent / "claim_rules.json"

#: 빈 줄로 나뉜 덩어리를 한 문단으로 본다. 표는 줄 사이에 빈 줄이 없으므로
#: 표 하나가 한 문단이 된다 — 머리글 칸과 값 칸이 서로 다른 줄에 있어도
#: 같은 문단에서 대조된다.
_PARAGRAPH = re.compile(r"\n\s*\n")


def load_rules(path: Path = RULES_FILE) -> list[dict]:
    """목록을 읽는다. 못 읽으면 빈 목록 — 훅이 세션을 막지 않는다."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rules = data.get("rules") if isinstance(data, dict) else None
    if not isinstance(rules, list):
        return []
    out = []
    for rule in rules:
        if not isinstance(rule, dict) or not rule.get("pattern"):
            continue
        try:
            compiled = re.compile(rule["pattern"])
            scope = re.compile(rule["scope"]) if rule.get("scope") else None
        except re.error:
            continue  # 목록의 흠 하나가 검사 전체를 멈추면 안 된다.
        out.append({**rule, "compiled": compiled, "scope_compiled": scope})
    return out


def load_history_files(path: Path = RULES_FILE) -> list[str]:
    """전문을 보지 않고 새로 더한 줄만 보는 파일 목록.

    `STATUS.md` 가 여기 있다. 그 파일은 날짜가 붙은 기록이고 지난 항목은 그때
    그렇게 적었다는 사실 자체가 기록이므로 고쳐 쓰지 않는다. 대신 **새로 더하는
    줄**은 검사한다.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    names = data.get("history_files") if isinstance(data, dict) else None
    return [n for n in names if isinstance(n, str)] if isinstance(names, list) else []


def find_false_claims(text: str, rules: list[dict] | None = None) -> list[dict]:
    """되풀이된 틀린 주장들. 항목마다 처음 맞은 자리 하나만 보고한다."""
    rules = load_rules() if rules is None else rules
    prose = strip_code(text)
    hits: list[dict] = []
    for rule in rules:
        for para in _PARAGRAPH.split(prose):
            match = rule["compiled"].search(para)
            if not match:
                continue
            scope = rule["scope_compiled"]
            if scope is not None and not scope.search(para):
                continue
            hits.append(
                {
                    "name": rule.get("name", match.group(0)),
                    "found": match.group(0),
                    "why": rule.get("why", ""),
                    "instead": rule.get("instead", ""),
                }
            )
            break
    return hits


def build_message(hits: list[dict], where: str = "이 답") -> str:
    parts = [f"사실 확인 — {where}이 이미 틀린 것으로 확인된 주장을 다시 적었다."]
    for hit in hits:
        parts.append(f"  \"{hit['found']}\" ({hit['name']})")
        if hit["why"]:
            parts.append(f"    왜 틀렸나: {hit['why']}")
        if hit["instead"]:
            parts.append(f"    대신: {hit['instead']}")
    parts.append(
        "목록은 harness/claim_rules.json 이다. 틀린 문장을 이름으로 부를 때는 "
        "백틱으로 감싸면 이 검사가 건너뛴다."
    )
    return "\n".join(parts)


def _marker(session_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", session_id or "unknown")[:80]
    return REPO / ".casa" / "harness" / f"claim_check_{safe}.marker"


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    if not isinstance(payload, dict):
        return 0
    if payload.get("stop_hook_active"):
        return 0

    entry = load_gates().get("claim_check")
    entry = entry if isinstance(entry, dict) else {}
    if entry.get("state", "on") != "on":
        return 0

    message = payload.get("last_assistant_message")
    if not isinstance(message, str) or not message.strip():
        return 0

    hits = find_false_claims(message)
    if not hits:
        return 0

    marker = _marker(str(payload.get("session_id", "")))
    if marker.exists():
        return 0
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("blocked once\n", encoding="utf-8")
    except OSError:
        pass  # 마커를 못 써도 차단은 한다.

    sys.stderr.write(
        build_message(hits) + "\n이 검사는 세션당 한 번만 뜬다.\n"
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
