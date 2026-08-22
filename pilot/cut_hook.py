#!/usr/bin/env python3
"""PreToolUse 훅: 초반에 코드를 안 연 세션을 그 자리에서 끊는다.

**왜 이것을 재는가.** `docs/EARLY_SIGNAL_RESULTS.md` 에서 초반 10호출에 `.py`
파일을 하나라도 열었는지가 그 세션이 일을 해낼지와 함께 간다는 것이 나왔다
(사슬 하나씩 빼고 맞혀 72.5%, 기준선 65.2%). `docs/PROCESS_DIFFERENCE_RESULTS.md`
에서 그 신호가 잡는 것이 **읽기와 계획으로 흘러간 세션**이라는 것도 나왔다 —
안 연 세션 16개 중 11개가 `HANDOFF.md` 말고는 한 줄도 안 고쳤다.

**남은 물음은 끊어서 이득인가다.** 판별 가능성과 끊기의 이득은 다른 질문이고,
앞선 배치는 아무 세션도 끊지 않았다. 이 훅이 끊는 쪽 조건을 만든다.

**이득을 "아낀 호출"로 계산하지 않는다**(2026-08-22 유저 지적). 예산이 작으면
아낄 것이 적고 재시작한 세션도 방향 잡기를 다시 한다. 계산은 **뽑기를 바꾸는
것**이다 — 그대로 두면 항목을 늘릴 확률이 33%인 세션을, 10호출을 버리고 65%
짜리로 바꾸는 거래다. 그래서 두 조건에서 **도구 호출 총량**을 같게 맞추고
"같은 총량으로 어느 쪽이 더 높은 상태에 도달하는가"를 묻는다.

**강제는 코드에 있다.** 프롬프트에 "코드를 먼저 열어라"를 넣으면 그것이 바로
우리가 검출하려는 차이를 없앤다(`harness/anchor.md`).

설정은 러너가 작업 디렉토리 밖에 써 둔다 — 세션이 읽으면 안 된다:

    .casa-cut.json   {"at": 10}
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

CONFIG_NAME = ".casa-cut.json"

#: 대상이 들어 있을 만한 열쇠. 앞에서부터 처음 찾은 것을 쓴다.
TARGET_KEYS = ("file_path", "path", "notebook_path", "pattern", "command")

CUT_MESSAGE = (
    "이번 세션은 여기서 끝낸다. 더 이상 도구를 쓸 수 없다. "
    "지금까지 본 것을 마지막 메시지로 정리하고 종료하라."
)


def target_of(call: dict) -> str:
    got = call.get("input") or {}
    for key in TARGET_KEYS:
        value = got.get(key)
        if isinstance(value, str):
            return value
    return ""


def tool_calls(path: Path) -> list[dict]:
    """트랜스크립트의 도구 호출. 알 수 없는 줄은 건너뛴다."""
    out: list[dict] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for line in text.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        message = row.get("message")
        if not isinstance(message, dict):
            continue
        for block in message.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                out.append({"name": block.get("name") or "?",
                            "input": block.get("input") or {}})
    return out


def opened_code(calls: list[dict]) -> bool:
    """이 구간에서 `.py` 파일을 하나라도 향한 호출이 있었는가."""
    return any(target_of(call).endswith(".py") for call in calls)


def decide(calls: list[dict], at: int) -> bool:
    """지금 끊어야 하는가.

    **`at` 호출째까지 코드를 한 번도 안 열었으면 끊는다.** 그 뒤로는 판정하지
    않는다 — 한 번 통과한 세션을 나중에 다시 재면 끊는 자리가 신호가 아니라
    그 세션의 길이에 좌우된다.
    """
    if at <= 0 or len(calls) < at:
        return False
    return not opened_code(calls[:at])


def load_config(start: Path) -> dict:
    """설정을 위로 거슬러 찾는다. 세션의 작업 트리 밖에 있다."""
    here = Path(start)
    for folder in (here, *here.parents):
        try:
            raw = json.loads((folder / CONFIG_NAME).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(raw, dict):
            return raw
    return {}


def install(workdir: Path, at: int) -> None:
    """끊는 시점을 적어 두고 훅을 배선한다.

    **설정은 작업 디렉토리 밖에 둔다** — 세션이 읽으면 그것을 보고 행동을
    바꾸고, 그러면 재려던 것이 사라진다. 예산 설정을 옮긴 것과 같은 이유다.

    **예산 훅을 덮지 않고 그 뒤에 붙인다.** 예산 훅이 `PreToolUse` 목록을
    통째로 쓰므로 이 함수가 나중에 불려야 한다. 순서가 뒤집히면 끊는 장치가
    조용히 사라지고, 두 조건이 같아진 채로 배치가 돈다.
    """
    if at <= 0:
        return
    workdir = Path(workdir)
    folder = workdir.parent
    folder.mkdir(parents=True, exist_ok=True)
    (folder / CONFIG_NAME).write_text(json.dumps({"at": at}, indent=2),
                                      encoding="utf-8")

    settings_path = workdir / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings: dict = {}
    if settings_path.is_file():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except ValueError:
            settings = {}
    command = f'"{sys.executable}" "{Path(__file__).resolve()}"'
    entry = {"matcher": "*",
             "hooks": [{"type": "command", "command": command}]}
    hooks = settings.setdefault("hooks", {})
    before = [e for e in hooks.get("PreToolUse", [])
              if json.dumps(e, sort_keys=True) != json.dumps(entry, sort_keys=True)]
    hooks["PreToolUse"] = [*before, entry]
    settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    if not isinstance(payload, dict):
        return 0

    workdir = Path(payload.get("cwd") or os.getcwd())
    at = load_config(workdir).get("at")
    if not isinstance(at, int) or at <= 0:
        return 0

    transcript = payload.get("transcript_path")
    if not isinstance(transcript, str):
        return 0

    if decide(tool_calls(Path(transcript)), at):
        sys.stderr.write(CUT_MESSAGE + "\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
