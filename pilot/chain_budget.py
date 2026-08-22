#!/usr/bin/env python3
"""PreToolUse hook: enforce a per-session tool-call budget in chain runs.

A chain splits one project across several sessions, and the split has to be
imposed rather than left to the agent — otherwise where a session stops is
chosen by the thing being measured (docs/MULTISESSION_ARM.md section 5).
The CLI has no turn cap, so the budget is enforced here, in code, which is
also this project's standing rule about enforcement.

두 단계다. **세션에게 남은 호출 수를 알려 주지 않는다**(2026-08-21 유저
지시로 바꿨다).

    stop       정해 둔 시점에 **한 번만** "이번 세션을 마무리하고 인계 문서를
               쓰고 끝내라"고 보낸다. 수는 말하지 않는다.
    block      상한(`hard_cap`)에서 도구 호출을 막는다. 세션이 정리 신호를
               무시하고 계속 갈 때만 닿는 안전판이다. 세션은 마지막 텍스트
               메시지를 낼 수 있다.

**왜 수를 말하지 않는가.** 2026-08-21 보정 사슬 여덟 세션 전부가 종료
메시지에서 예산을 이유로 들었고, 넷은 그래서 편집을 시작하지 않았다고 적었다.
세션 1은 "남은 2회로는 편집을 시작하지 않겠다"고 했고, 세션 4는 34/30에서
멈췄는데 상한 45까지 11회가 남아 있었다. 남은 수를 알려 주는 한 세션은 그 수를
보고 일을 조절하므로, 세션이 멈추는 자리를 측정 대상이 정하게 된다
(docs/MULTISESSION_ARM.md 5절이 금지하는 것이다).

**왜 한 번만 보내는가.** 호출마다 되풀이하면 그 자체가 남은 분량을 알려 주는
신호가 된다 — 세션이 같은 말을 몇 번 들었는지로 위치를 셀 수 있다.

**시점을 정하는 것은 코드다.** 이 프로젝트의 규칙은 강제가 프롬프트가 아니라
코드에 있어야 한다는 것이다. 훅이 세션에게 말을 거는 수단이 글자일 뿐,
언제 끊을지는 여기서 정한다.

Configuration comes from the workdir, written by the chain runner:

    .casa-chain.json   {"budget": 30, "warn_at": 25, "hard_cap": 45}

`warn_at` 이 정리 신호를 보내는 시점이다. 이름은 앞선 배치들의 기록과 맞추기
위해 그대로 둔다.
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


def config_dir(workdir: Path) -> Path:
    """설정 파일을 두는 자리 — **세션의 작업 트리 밖이다.**

    두 러너 모두 작업 디렉토리를 `out_dir / <이름>` 으로 만드므로 부모가
    수집 결과 디렉토리다. 훅은 `load_config` 가 위로 거슬러 올라가며 찾으니
    거기 두어도 읽는다.

    **작업 트리 안에 두면 안 되는 이유:** 세션이 `ls` 한 번으로 볼 수 있고,
    열면 예산과 상한이 그대로 적혀 있다. 2026-08-21에 훅 메시지에서 수를
    빼기로 했는데, 파일이 트리 안에 있으면 그 뜻이 없어진다.
    """
    return workdir.parent if workdir.parent != workdir else workdir


def hard_cap_for(budget: int) -> int | None:
    """예산을 넘어도 되는 데까지. 넘는 것은 허용하되 과하게는 안 된다.

    예산의 절반만큼 더 준다(최소 10회). 예산 30이면 45다. 세션이 하던
    서브시스템 하나를 끝내기에는 넉넉하고, 두셋을 더 하기에는 모자란다.

    **예산이 0 이하면 상한도 없다** — 호출 수로는 아무것도 제한하지 않고
    시간으로만 제한하는 갈래다.
    """
    if budget <= 0:
        return None
    return budget + max(10, budget // 2)


def install(workdir: Path, budget: int, warn_margin: int = 5,
            hard_cap: int | None = None) -> None:
    """예산 훅을 작업 디렉토리에 배선한다.

    사슬 러너와 단발 러너가 함께 쓴다. 전역이 아니라 작업 디렉토리마다
    쓰므로, 수집 실행의 설정이 개발자 자신의 세션으로 새지 않는다.

    `.claude/settings.json` 은 덮지 않고 합친다 — 스냅숏 훅이 이미 쓰여
    있을 수 있다.

    **`budget` 이 0 이하면 아무것도 배선하지 않는다**(2026-08-21 유저 지시).
    보정 사슬 여덟 세션 전부가 종료 메시지에서 예산을 이유로 들었고 넷은
    그래서 편집을 시작하지 않았다고 적었다. 세션 4는 34/30 에서 멈췄는데
    상한 45 까지 11회가 남아 있었다. 남은 호출 수를 알려 주는 한 세션은 그
    수를 보고 일을 조절하므로, 세션이 멈추는 자리를 측정 대상이 정하게 된다.
    그래서 세션에게 아무 신호도 주지 않고 시간으로만 제한하는 갈래를 둔다.
    """
    import sys as _sys

    if budget <= 0:
        return

    config_dir(workdir).mkdir(parents=True, exist_ok=True)
    (config_dir(workdir) / CONFIG_NAME).write_text(
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


def find_config(start: Path) -> tuple[Path | None, dict]:
    """설정 파일이 있던 폴더와 그 내용. 못 찾으면 `(None, {})`."""
    here = Path(start)
    for folder in (here, *here.parents):
        try:
            raw = json.loads((folder / CONFIG_NAME).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(raw, dict):
            return folder, raw
    return None, {}


def load_config(start: Path) -> dict:
    """작업 디렉토리에서 사슬 설정을 읽는다. **위로 거슬러 올라가며 찾는다.**

    훅이 받는 `cwd`는 세션이 마지막으로 있던 자리라 작업 트리 뿌리가 아닐 수
    있다. git 이 저장소 뿌리를 찾는 것과 같은 방식으로 위로 올라가며 찾는다.

    2026-08-21에 설정을 못 찾아 **기본값(60)으로 조용히 떨어진 적이 있다** —
    100으로 준 예산이 60으로 깎여 세션이 61호출에서 잘렸고 실패로도 안 보였다.
    지금은 `main()` 이 설정을 못 찾으면 아무것도 하지 않는다. 못 찾은 채로
    세션을 자르는 것보다, 안 자르고 실행 기록에 호출 수가 그대로 남는 편이
    낫다 — 뒤의 것은 요약에서 드러나지만 앞의 것은 안 드러난다.
    """
    return find_config(start)[1]


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


STOP_MESSAGE = (
    "이번 세션은 여기까지 하고 끝낸다. 하던 것을 마무리하고, 한 일과 남은 일과 "
    "다음 사람이 먼저 볼 것을 저장소의 인계 문서에 적고 종료하라. 새로 시작하는 "
    "작업은 다음 세션이 이어받는다."
)

BLOCK_MESSAGE = (
    "더 이상 도구를 쓸 수 없다. 지금까지 한 일과 다음에 이어서 할 일을 마지막 "
    "메시지로 정리하고 끝내라."
)


def decide(used: int, budget: int, warn_at: int,
           hard_cap: int | None = None,
           already_said: bool = False) -> tuple[int, str]:
    """(exit code, message). Exit 2 blocks the call; 0 lets it through.

    **어떤 메시지에도 수가 들어가지 않는다.** 남은 호출 수를 알려 주면 세션이
    그것을 보고 일을 조절한다 — 모듈 설명의 근거 참조.

    정리 신호는 `already_said` 가 참이면 보내지 않는다. 호출마다 되풀이하면
    들은 횟수로 위치를 셀 수 있게 되어, 수를 감춘 뜻이 없어진다.
    """
    if budget <= 0:
        return 0, ""          # 호출 수로는 제한하지 않는다.
    cap = hard_cap or hard_cap_for(budget)
    if used >= cap:
        return 2, BLOCK_MESSAGE
    if used >= warn_at and not already_said:
        return 0, STOP_MESSAGE
    return 0, ""


SAID_NAME = ".casa-chain-said.json"


def _said_path(folder: Path) -> Path:
    """정리 신호를 이미 보낸 세션을 적어 두는 파일.

    설정 파일과 같은 자리에 둔다 — 세션의 작업 트리 밖이다. 사슬의 세션들이
    작업 디렉토리를 함께 쓰므로 세션마다 갈라 적어야 하고, 트랜스크립트 파일
    이름이 세션마다 다르므로 그것을 열쇠로 쓴다.
    """
    return folder / SAID_NAME


def _already_said(path: Path, key: str) -> bool:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(raw, dict) and bool(raw.get(key))


def _remember_said(path: Path, key: str) -> None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raw = {}
    except (OSError, ValueError):
        raw = {}
    raw[key] = True
    try:
        path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    except OSError:
        pass          # 기억하지 못하면 한 번 더 보낼 뿐, 세션을 막지 않는다.


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    if not isinstance(payload, dict):
        return 0

    workdir = Path(payload.get("cwd") or os.getcwd())
    folder, config = find_config(workdir)
    if folder is None:
        return 0
    budget = config.get("budget", DEFAULT_BUDGET)
    if not isinstance(budget, int) or budget <= 0:
        return 0
    warn_at = config.get("warn_at", max(1, budget - DEFAULT_WARN_MARGIN))

    transcript = payload.get("transcript_path")
    if not isinstance(transcript, str):
        return 0
    used = count_tool_calls(Path(transcript))

    said_path = _said_path(folder)
    key = Path(transcript).name
    code, message = decide(used, budget, warn_at, config.get("hard_cap"),
                           already_said=_already_said(said_path, key))
    if code == 2:
        sys.stderr.write(message + "\n")
        return 2
    if message:
        _remember_said(said_path, key)
        json.dump({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "additionalContext": message}},
            sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
