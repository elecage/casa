#!/usr/bin/env python3
"""Stop 훅: 마지막 보고가 내부 약어투성이면 한 번 되돌려보낸다.

유저 지적(2026-07-24): "네가 아는 용어로만 말하면 내가 어떻게 알아듣냐,
제대로 분석했는지도 의심스럽다." 보고를 유저가 검증할 수 없으면 결과가
맞는지 틀리는지도 확인이 안 된다.

검출 대상 둘:
  - 내부 라벨 (RQ2, F1, G3, W15, H1b 등) — 이 저장소 밖에서는 뜻이 없다.
  - 정의 없이 쓴 통계 용어 (AUROC, Brier, ECE 등) — 첫 사용 시 한 줄 정의가
    붙어야 한다.

**세션당 한 번만** 차단한다(루프 방지). 계약: stdin JSON의
`last_assistant_message`가 마지막 보고문, exit 2면 종료를 막고 stderr가
모델에 전달된다.
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

# 이 저장소 안에서만 뜻이 통하는 라벨.
#
# 한국어 조사가 라벨에 바로 붙는다 ("F1이", "W15에"). 파이썬의 \b는 한글을
# 단어 문자로 보므로 그 자리에 경계가 생기지 않아 전부 놓친다. 그래서 경계를
# "영숫자가 아니면 끝"으로 직접 쓴다.
_L = r"(?<![0-9A-Za-z])"
_R = r"(?![0-9A-Za-z])"
INTERNAL_LABELS = [
    re.compile(_L + r"RQ\s?[1-9]" + _R),
    re.compile(_L + r"H1[ab]" + _R),
    re.compile(_L + r"G[1-3]" + _R),
    re.compile(_L + r"W\d{1,2}(?:[.-]\d)?" + _R),
    # F1은 표준 지표 이름(F1 스코어)이기도 하므로 그 용법은 뺀다.
    re.compile(_L + r"F[1-9]" + _R + r"(?!\s*(?:스코어|점수|score))", re.IGNORECASE),
]
# 첫 사용 시 정의가 필요한 통계 용어.
STAT_TERMS = [
    re.compile(r"AUROC", re.IGNORECASE),
    re.compile(r"\bBrier\b", re.IGNORECASE),
    re.compile(r"\bECE" + _R),
    re.compile(r"pass\^k"),
    re.compile(r"\bp-?value\b", re.IGNORECASE),
]
# 정의가 붙었다고 볼 표시 (용어 직후 60자 안).
_DEFINED = re.compile(r"[(（=:：—-]")
_WINDOW = 60


def find_internal_labels(text: str) -> list[str]:
    hits: list[str] = []
    for pat in INTERNAL_LABELS:
        for m in pat.finditer(text):
            token = m.group(0)
            if token not in hits:
                hits.append(token)
    return hits


def find_undefined_stats(text: str) -> list[str]:
    hits: list[str] = []
    for pat in STAT_TERMS:
        m = pat.search(text)
        if not m:
            continue
        tail = text[m.end() : m.end() + _WINDOW]
        if _DEFINED.search(tail):
            continue
        token = m.group(0)
        if token not in hits:
            hits.append(token)
    return hits


def build_message(labels: list[str], stats: list[str]) -> str:
    parts = ["보고 규율 검사 — 이 보고는 유저가 검증할 수 없다."]
    if labels:
        parts.append(f"내부 라벨을 풀어 쓰지 않았다: {', '.join(labels)}")
    if stats:
        parts.append(f"정의 없이 쓴 통계 용어: {', '.join(stats)}")
    parts.append(
        "다시 쓸 것: (1) 저장소 안에서만 통하는 라벨 대신 현상을 문장으로 "
        "서술하고, (2) 통계 용어는 첫 사용 시 한 줄 정의를 붙이고, "
        "(3) 핵심 주장마다 원자료 수치나 재현 명령을 같이 낸다. "
        "이 검사는 세션당 한 번만 뜬다."
    )
    return "\n".join(parts)


def _marker(session_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", session_id or "unknown")[:80]
    return REPO / ".casa" / "harness" / f"report_check_{safe}.marker"


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    if not isinstance(payload, dict):
        return 0
    # 이 훅 때문에 이미 한 번 이어졌다면 다시 막지 않는다.
    if payload.get("stop_hook_active"):
        return 0

    gates = load_gates()
    entry = gates.get("report_check")
    entry = entry if isinstance(entry, dict) else {}
    if entry.get("state", "on") != "on":
        return 0
    threshold = entry.get("threshold", 2)
    if not isinstance(threshold, int) or threshold < 1:
        threshold = 2

    message = payload.get("last_assistant_message")
    if not isinstance(message, str) or not message.strip():
        return 0

    labels = find_internal_labels(message)
    stats = find_undefined_stats(message)
    if len(labels) + len(stats) < threshold:
        return 0

    marker = _marker(str(payload.get("session_id", "")))
    if marker.exists():
        return 0
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("blocked once\n", encoding="utf-8")
    except OSError:
        pass  # 마커를 못 써도 차단은 한다 (다음 번에 또 뜰 뿐).

    sys.stderr.write(build_message(labels, stats) + "\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
