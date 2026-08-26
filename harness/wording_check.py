#!/usr/bin/env python3
"""Stop 훅: 마지막 답이 글쓰기 규칙을 어겼으면 한 번 되돌려보낸다.

**왜 이 훅이 있나 (2026-08-24 유저 지시).** 유저 물음 — "지금의 경우에도 네가
스스로 오류를 찾아내는 것이 아니고 나와의 인터랙션에 의해서 나오잖아. 이걸
네가 나인 것처럼 모사하는 훅을 만들 수 있냐는거야."

유저가 하는 지적은 세 종류다. 이 훅은 **첫째 종류**를 담당한다 — 글로 적힌
규칙을 어긴 것. 위반이 답의 문자열 안에 그대로 있으므로 목록 대조로 판정되고
판단이 필요 없다. (둘째 종류는 `repeat_check.py`, 셋째 종류인 설계의 모순은
결정론으로 판정되지 않는다.)

**규칙은 `CLAUDE.md` 의 "How to write" 절과 "구어체를 쓰지 않는다" 절이고,
목록은 `harness/wording_rules.json` 에 있다.** 목록이 따로 있는 이유는 **유저
지적 하나가 항목 하나가 되기 때문**이다. 2026-08-24 세션이 "갈리다" 를 한 번
지적받고 같은 세션 안에서 다시 썼다 — 목록이 있었으면 두 번째에서
되돌아왔다.

**금지어를 이름으로 부를 때는 백틱으로 감싼다.** 이 훅은 인라인 코드와 코드
블록과 인용 줄을 빼고 본다. 그렇게 하지 않으면 위반을 정정하는 답 자체가
차단된다.

**세션당 한 번만** 차단한다(되풀이 방지). 계약: stdin JSON의
`last_assistant_message` 가 마지막 답, exit 2면 종료를 막고 stderr 가 모델에
전달된다.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gates import REPO, load_gates  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

RULES_FILE = Path(__file__).resolve().parent / "wording_rules.json"

#: 코드 블록, 인라인 코드, 인용 줄. 이 안의 글자는 보지 않는다.
_FENCE = re.compile(r"```.*?```", re.DOTALL)
_INLINE = re.compile(r"`[^`\n]*`")
_QUOTE = re.compile(r"^\s*>.*$", re.MULTILINE)

#: 분모를 안 밝힌 비율. 경로·판·날짜와 겹치지 않도록 양옆에 숫자·점·빗금이
#: 오면 뺀다. 유저 지적(2026-08-23) — "47/48, 18/18, 9/10 이렇게 말하면 이게
#: 뭔지 어떻게 알아?"
_BARE_RATIO = re.compile(r"(?<![0-9./])([0-9]{1,4})/([0-9]{1,4})(?![0-9./])")

#: 그 비율이 무엇의 비율인지 밝혔다고 볼 표시. 앞뒤 이 길이 안에서 찾는다.
#:
#: **좁게 잡는다.** 처음에는 "세션 수" 같은 말도 밝힌 것으로 봤는데, 그러면
#: "맞힌 세션 수는 47/48 이다" 가 통과한다. 유저가 지적한 것이 정확히 그
#: 문장이다 — 분자와 분모가 각각 무엇인지가 안 적혀 있다. "48세션 중 47" 처럼
#: 두 수를 잇는 구문이 있어야 밝힌 것으로 본다.
_RATIO_EXPLAINED = re.compile(r"중 |중에|가운데|분의|나눈")
_RATIO_WINDOW = 40


#: 표의 줄. 비율 검사에서만 뺀다 — 표 안의 수는 머리글이 무엇의 수인지 적는다.
_TABLE_ROW = re.compile(r"^.*\|.*$", re.MULTILINE)


def strip_code(text: str) -> str:
    """코드 블록·인라인 코드·인용 줄을 빼고 남은 산문."""
    text = _FENCE.sub(" ", text)
    text = _INLINE.sub(" ", text)
    return _QUOTE.sub(" ", text)


def strip_tables(text: str) -> str:
    """표의 줄을 뺀다. 비율 검사에만 쓴다."""
    return _TABLE_ROW.sub(" ", text)


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
        except re.error:
            continue  # 목록의 흠 하나가 검사 전체를 멈추면 안 된다.
        out.append({**rule, "compiled": compiled})
    return out


def find_violations(text: str, rules: list[dict] | None = None) -> list[dict]:
    """어긴 항목들. 항목마다 처음 맞은 자리 하나만 보고한다."""
    rules = load_rules() if rules is None else rules
    prose = strip_code(text)
    hits = []
    for rule in rules:
        match = rule["compiled"].search(prose)
        if match:
            hits.append({"name": rule.get("name", match.group(0)),
                         "kind": rule.get("kind", ""),
                         "found": match.group(0),
                         "instead": rule.get("instead", "")})
    return hits


def find_bare_ratios(text: str) -> list[str]:
    """분모가 무엇인지 안 밝힌 비율. 산문에서만 본다.

    표 안의 수는 세지 않는다 — 머리글이 무엇의 수인지 적는다. 이 세션의 실제
    기록 답 1123개에 실행해 보니, 표를 빼지 않으면 검출된 것의 대부분이
    표의 값이었다.
    """
    prose = strip_tables(strip_code(text))
    out: list[str] = []
    for match in _BARE_RATIO.finditer(prose):
        start = max(match.start() - _RATIO_WINDOW, 0)
        window = prose[start : match.end() + _RATIO_WINDOW]
        if _RATIO_EXPLAINED.search(window):
            continue
        token = match.group(0)
        if token not in out:
            out.append(token)
    return out


def build_message(hits: list[dict], ratios: list[str]) -> str:
    parts = ["글쓰기 규칙 검사 — 이 답은 CLAUDE.md 의 글쓰기 규칙을 어겼다."]
    for hit in hits:
        kind = f"[{hit['kind']}] " if hit["kind"] else ""
        parts.append(f"  {kind}\"{hit['found']}\" ({hit['name']}) "
                     f"-> {hit['instead']}")
    if ratios:
        parts.append("  분모를 안 밝힌 비율: " + ", ".join(ratios)
                     + " -> 분자와 분모가 각각 무엇인지 문장으로 적는다")
    parts.append(
        "다시 쓸 것. 규칙은 CLAUDE.md 의 'How to write' 절과 '구어체를 쓰지 "
        "않는다' 절이고 목록은 harness/wording_rules.json 이다. "
        "금지어를 이름으로 부를 때는 백틱으로 감싸면 이 검사가 건너뛴다. "
        "이 검사는 세션당 한 번만 뜬다."
    )
    return "\n".join(parts)


def _marker(session_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", session_id or "unknown")[:80]
    return REPO / ".casa" / "harness" / f"wording_check_{safe}.marker"


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    if not isinstance(payload, dict):
        return 0
    if payload.get("stop_hook_active"):
        return 0

    entry = load_gates().get("wording_check")
    entry = entry if isinstance(entry, dict) else {}
    if entry.get("state", "on") != "on":
        return 0

    message = payload.get("last_assistant_message")
    if not isinstance(message, str) or not message.strip():
        return 0

    hits = find_violations(message)
    ratios = find_bare_ratios(message)
    if not hits and not ratios:
        return 0

    marker = _marker(str(payload.get("session_id", "")))
    if marker.exists():
        return 0
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("blocked once\n", encoding="utf-8")
    except OSError:
        pass  # 마커를 못 써도 차단은 한다.

    sys.stderr.write(build_message(hits, ratios) + "\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
