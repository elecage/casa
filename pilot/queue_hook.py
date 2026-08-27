#!/usr/bin/env python3
"""PostToolUse 훅: 세션이 항목을 끝냈다고 적으면 `NEXT.md` 를 다시 쓴다.

**과제의 장치이지 규칙 강제가 아니다.** `CLAUDE.md` 의 첫 설계 원칙 둘째 따름
정리는 **연구 대상 세션에게 주는 규칙을 훅으로 강제하지 말라**고 한다. 이 훅은
아무것도 막지 않고 아무것도 요구하지 않는다 — 큐가 다음 항목을 드러내는
동작이 세션의 편집에 반응해야 해서 있는 것이고, 빌드 도구가 파일 변경에
반응하는 것과 같은 자리다. 규율(항목마다 `docs/decisions.md` 갱신)을 지켰는지는
채점기가 따로 판정하고, 이 훅은 그것을 강제하지 않는다.

**왜 훅인가.** `NEXT.md` 는 `docs/decisions.md` 의 내용으로 정해진다
(`pilot/queue_task.py`). 세션이 그 파일에 줄을 적은 뒤 `NEXT.md` 를 다시 열면
다음 항목이 보여야 하는데, 러너가 세션 시작 때 한 번만 쓰면 세션 하나가 항목
하나밖에 못 한다.

이 훅은 **절대 세션을 막지 않는다.** 무슨 일이 있어도 0으로 끝난다.

설정은 러너가 작업 디렉토리에 써 둔다:

    .casa-queue.json   {"task": "queue-flat"}
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from queue_task import write_next  # noqa: E402

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

CONFIG_NAME = ".casa-queue.json"


def load_task(workdir: Path) -> str | None:
    """이 작업 디렉토리가 어느 큐 과제인가."""
    try:
        data = json.loads((Path(workdir) / CONFIG_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    task = data.get("task") if isinstance(data, dict) else None
    return task if isinstance(task, str) and task else None


def refresh(workdir: Path) -> str | None:
    """`NEXT.md` 를 지금 상태에 맞게 다시 쓴다. 과제가 아니면 아무것도 안 한다."""
    task = load_task(workdir)
    if task is None:
        return None
    return write_next(Path(workdir), task=task)


def prepare(workdir: Path, task: str) -> None:
    """설정을 쓰고 `NEXT.md` 를 만든다. 훅 배선은 하지 않는다.

    **스냅숏 훅을 배선하기 전에 부른다.** 스냅숏 저장소는 세션이 시작하기 전
    상태를 커밋 하나로 찍어 두는데(`pilot/snapshot.py` 의 `_baseline`),
    `NEXT.md` 는 그 시작 상태의 일부다. 뒤에 만들면 세션이 만든 것처럼 첫 호출의
    변경에 들어간다.
    """
    workdir = Path(workdir).resolve()
    (workdir / CONFIG_NAME).write_text(
        json.dumps({"task": task}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    write_next(workdir, task=task)


def install(workdir: Path, task: str) -> None:
    """`prepare` 한 다음 훅을 배선한다.

    **`PostToolUse` 목록의 맨 앞에 넣는다.** 스냅숏 훅이 뒤에 있어야 이번
    호출의 스냅숏에 갱신된 `NEXT.md` 가 담긴다. 그리고 이미 있는 목록을
    덮지 않는다 — 스냅숏 훅이 먼저 배선되어 있다.
    """
    workdir = Path(workdir).resolve()
    prepare(workdir, task)

    settings_path = workdir / ".claude" / "settings.json"
    settings_path.parent.mkdir(exist_ok=True)
    settings: dict = {}
    if settings_path.is_file():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except ValueError:
            settings = {}
    hooks = settings.setdefault("hooks", {})
    command = f'"{sys.executable}" "{Path(__file__).resolve()}"'
    entry = {"matcher": "*",
             "hooks": [{"type": "command", "command": command}]}
    existing = hooks.get("PostToolUse")
    existing = existing if isinstance(existing, list) else []
    # 다시 배선해도 같은 것이 쌓이지 않게 한다 — 사슬은 세션마다 배선한다.
    existing = [e for e in existing if json.dumps(e) != json.dumps(entry)]
    hooks["PostToolUse"] = [entry, *existing]
    settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def main() -> int:
    try:
        sys.stdin.read()                 # 훅 입력은 읽고 버린다
        refresh(Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd()))
    except Exception:                    # noqa: BLE001 - 장치가 세션을 죽이면 안 된다
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
