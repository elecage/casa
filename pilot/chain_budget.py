#!/usr/bin/env python3
"""PreToolUse hook: enforce a per-session tool-call budget in chain runs.

A chain splits one project across several sessions, and the split has to be
imposed rather than left to the agent — otherwise where a session stops is
chosen by the thing being measured (docs/MULTISESSION_ARM.md section 5).
The CLI has no turn cap, so the budget is enforced here, in code, which is
also this project's standing rule about enforcement.

세 단계다. **예산은 가위가 아니라 안전판이다**(2026-08-21 유저 지시).

    warning    예산에 닿기 몇 호출 전, 몇 회 남았는지 알려 준다. 이 창이
               없으면 인계 문서를 쓸 수가 없다 — 파일을 쓰는 것도 도구 호출
               이고, 인계는 이 갈래가 재려는 것이기 때문이다.
    over       **예산을 넘어도 막지 않는다.** 넘었다는 것과 얼마나 넘었는지를
               알려 주고, 하던 것을 마무리하라고 말한다.
    block      상한(`hard_cap`)에서 도구 호출을 막는다. 세션은 마지막 텍스트
               메시지를 낼 수 있다.

**왜 넘게 두는가.** 예산에서 딱 자르면 세션이 서브시스템 중간에서 끊긴다.
그러면 어디서 멈췄는지가 일의 양이 아니라 우리가 넣은 수가 정한 것이 된다.
일의 양은 서브시스템마다 다르고, 세션이 조금 넘겨서 하던 것을 끝내는 것은
실제 작업에서 일어나는 일이다. **다만 과하게 넘어가면 안 된다** — 그래서
상한을 둔다. 그리고 **얼마나 넘었는지가 그 서브시스템의 구현량을 재는
값이다.** 어떤 서브시스템에서 늘 크게 넘으면 그 서브시스템이 큰 것이다.

"경고를 받고 인계를 남겼는가"와 "얼마나 넘겼는가"가 둘 다 관측 대상이지
전제가 아니다.

Configuration comes from the workdir, written by the chain runner:

    .casa-chain.json   {"budget": 30, "warn_at": 25, "hard_cap": 45}
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_BUDGET = 60
DEFAULT_WARN_MARGIN = 5
CONFIG_NAME = ".casa-chain.json"


def hard_cap_for(budget: int) -> int:
    """예산을 넘어도 되는 데까지. 넘는 것은 허용하되 과하게는 안 된다.

    예산의 절반만큼 더 준다(최소 10회). 예산 30이면 45다. 세션이 하던
    서브시스템 하나를 끝내기에는 넉넉하고, 두셋을 더 하기에는 모자란다.
    """
    return budget + max(10, budget // 2)


def install(workdir: Path, budget: int, warn_margin: int = 5,
            hard_cap: int | None = None) -> None:
    """예산 훅을 작업 디렉토리에 배선한다.

    사슬 러너와 단발 러너가 함께 쓴다. 전역이 아니라 작업 디렉토리마다
    쓰므로, 수집 실행의 설정이 개발자 자신의 세션으로 새지 않는다.

    `.claude/settings.json` 은 덮지 않고 합친다 — 스냅숏 훅이 이미 쓰여
    있을 수 있다.
    """
    import sys as _sys

    (workdir / CONFIG_NAME).write_text(
        json.dumps({"budget": budget,
                    "warn_at": max(1, budget - warn_margin),
                    "hard_cap": hard_cap or hard_cap_for(budget)}, indent=2),
        encoding="utf-8")
    settings_path = workdir / ".claude" / "settings.json"
    settings_path.parent.mkdir(exist_ok=True)
    settings = {}
    if settings_path.is_file():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except ValueError:
            settings = {}
    command = f'"{_sys.executable}" "{Path(__file__).resolve()}"'
    settings.setdefault("hooks", {})["PreToolUse"] = [
        {"matcher": "*", "hooks": [{"type": "command", "command": command}]}]
    settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def load_config(start: Path) -> dict:
    """작업 디렉토리에서 사슬 설정을 읽는다. **위로 거슬러 올라가며 찾는다.**

    훅이 받는 `cwd`는 세션이 마지막으로 있던 자리라 작업 트리 뿌리가 아닐 수
    있다. 그러면 설정을 못 찾고 **기본값(60)으로 조용히 떨어진다** — 2026-08-21에
    100으로 준 예산이 60으로 깎여 세션이 61호출에서 잘렸고, 실패로도 안 보였다.
    git 이 저장소 뿌리를 찾는 것과 같은 방식으로 위로 올라가며 찾는다.
    """
    here = Path(start)
    for folder in (here, *here.parents):
        try:
            raw = json.loads((folder / CONFIG_NAME).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(raw, dict):
            return raw
    return {}


def count_tool_calls(transcript: Path) -> int:
    """Tool calls issued so far in this session.

    Counted from the transcript rather than kept in a side file: the
    transcript is the record the rest of the project already trusts, and a
    counter file would drift if the session were resumed.
    """
    total = 0
    try:
        text = transcript.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    for line in text.splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict) or entry.get("type") != "assistant":
            continue
        content = (entry.get("message") or {}).get("content")
        if isinstance(content, list):
            total += sum(1 for item in content
                         if isinstance(item, dict) and item.get("type") == "tool_use")
    return total


def decide(used: int, budget: int, warn_at: int,
           hard_cap: int | None = None) -> tuple[int, str]:
    """(exit code, message). Exit 2 blocks the call; 0 lets it through.

    **예산을 넘는 것 자체는 막지 않는다.** 막는 것은 상한뿐이다.
    """
    cap = hard_cap or hard_cap_for(budget)
    if used >= cap:
        return 2, (
            f"도구 호출 상한 — {used}회. 예산은 {budget}회였다.\n"
            "더 이상 도구를 쓸 수 없다. 지금까지 한 일과 다음에 이어서 할 일을 "
            "마지막 메시지로 정리하고 끝내라."
        )
    if used >= budget:
        return 0, (
            f"세션 예산을 넘었다 — 도구 호출 {used}회, 예산 {budget}회 "
            f"({used - budget}회 초과). 하던 것을 마무리하고, 지금까지 한 일과 "
            f"다음에 할 일을 저장소에 기록으로 남겨라. {cap}회에서 도구를 쓸 수 "
            "없게 된다."
        )
    if used >= warn_at:
        return 0, (
            f"세션 예산 경고 — 도구 호출 {used}/{budget}회. "
            f"{budget - used}회 남았다. 남은 호출 안에 작업 상태와 다음에 할 일을 "
            "저장소에 기록으로 남겨라."
        )
    return 0, ""


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    if not isinstance(payload, dict):
        return 0

    workdir = Path(payload.get("cwd") or os.getcwd())
    config = load_config(workdir)
    budget = config.get("budget", DEFAULT_BUDGET)
    if not isinstance(budget, int) or budget <= 0:
        return 0
    warn_at = config.get("warn_at", max(1, budget - DEFAULT_WARN_MARGIN))

    transcript = payload.get("transcript_path")
    if not isinstance(transcript, str):
        return 0
    used = count_tool_calls(Path(transcript))

    code, message = decide(used, budget, warn_at, config.get("hard_cap"))
    if code == 2:
        sys.stderr.write(message + "\n")
        return 2
    if message:
        json.dump({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "additionalContext": message}},
            sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
