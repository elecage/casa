#!/usr/bin/env python3
"""PostToolUse 훅: 파일이 바뀐 호출마다 작업 트리를 스냅숏한다.

**왜 필요한가.** 함정 판정의 절반은 "그 시점의 작업 트리"를 봐야 나온다 —
중복 구현이 그때 있었나, 경고가 그때도 남아 있었나. 최종 상태만 있으면
빠졌다가 나온 세션과 처음부터 안 빠진 세션이 구분되지 않는다
(`docs/RECOVERY_RULE.md` 4절).

**왜 별도 저장소인가.** 세션이 쓰는 저장소에 우리 커밋을 섞으면 세션이
`git log`에서 그것을 본다. 관측이 관측 대상을 바꾸면 안 된다. 그래서
`--git-dir`을 작업 트리 밖에 두고, 세션 쪽에는 아무 흔적도 남기지 않는다.

**왜 커밋인가.** 세션이 `sed`나 `python -c`로 파일을 바꿔도 잡힌다. 편집
도구 호출만 따라가면 셸 변경이 새고, `casa.progress`가 그 새는 양을 이미
재고 있다. git은 어떻게 바꿨든 결과를 본다.

이 훅은 **절대 세션을 막지 않는다.** 무슨 일이 있어도 0으로 끝난다 — 관측
장치가 관측 대상을 죽이면 안 된다.

설정은 러너가 작업 디렉토리에 써 둔다:

    .casa-snapshot.json   {"git_dir": "...", "state_dir": "..."}
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

CONFIG_NAME = ".casa-snapshot.json"

#: 스냅숏에서 빼는 것들. 우리가 심어 둔 설정 파일과 부산물이라 세션의
#: 작업이 아니다.
EXCLUDES = (".casa-chain.json", ".casa-snapshot.json", ".claude/",
            "__pycache__/", "*.pyc")


def _git(git_dir: Path, work_tree: Path, *args: str) -> subprocess.CompletedProcess:
    """작업 트리 **안에서** 실행한다.

    `git add -A` 는 현재 디렉토리를 기준으로 무엇을 담을지 정한다. 훅은 보통
    작업 트리 안에서 돌지만 그렇지 않을 때도 있고, 그때는 조용히 아무것도 안
    담는다 — 스냅숏이 비는데 실패로도 안 보인다.
    """
    # git 훅 안에서 돌면 부모 git 이 GIT_INDEX_FILE·GIT_DIR 같은 것을 물려준다.
    # 그대로 두면 `add` 가 **남의 색인**에 담기고, 스냅숏 저장소에는 담을 것이
    # 없어 커밋이 조용히 실패한다. 2026-08-20에 이것 때문에 커밋 훅에서만
    # 스냅숏이 비었다.
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(
        ["git", f"--git-dir={git_dir}", f"--work-tree={work_tree}", *args],
        cwd=work_tree, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace")


def install(workdir: Path, git_dir: Path) -> None:
    """스냅숏 저장소를 만들고 훅을 작업 디렉토리에 배선한다.

    이미 있는 `.claude/settings.json`은 덮어쓰지 않고 합친다 — 사슬 러너가
    거기에 예산 훅을 이미 써 두었다.
    """
    workdir, git_dir = Path(workdir), Path(git_dir)
    git_dir.parent.mkdir(parents=True, exist_ok=True)
    if not git_dir.exists():
        subprocess.run(["git", "init", "-q", "--bare", str(git_dir)], check=True)
        # 작업 트리를 따로 주므로 bare 로 두면 안 된다.
        subprocess.run(["git", f"--git-dir={git_dir}", "config", "core.bare",
                        "false"], check=True)
    (git_dir / "info").mkdir(exist_ok=True)
    (git_dir / "info" / "exclude").write_text(
        "\n".join(EXCLUDES) + "\n", encoding="utf-8")

    (workdir / CONFIG_NAME).write_text(json.dumps(
        {"git_dir": str(git_dir), "state_dir": str(git_dir)}, indent=2),
        encoding="utf-8")

    settings_path = workdir / ".claude" / "settings.json"
    settings_path.parent.mkdir(exist_ok=True)
    settings = {}
    if settings_path.is_file():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except ValueError:
            settings = {}
    hooks = settings.setdefault("hooks", {})
    command = f'"{sys.executable}" "{Path(__file__).resolve()}"'
    hooks["PostToolUse"] = [
        {"matcher": "*", "hooks": [{"type": "command", "command": command}]}]
    settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def _load_config(workdir: Path) -> dict | None:
    path = workdir / CONFIG_NAME
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None


def _next_index(state_dir: Path) -> int:
    """이 세션의 다음 호출 번호.

    세어 두는 파일은 **스냅숏 저장소 옆**에 둔다 — 저장소가 세션마다 하나이니
    번호도 세션마다 처음부터 올라간다. 2026-08-20 프로브에서 이 파일을 한 칸
    위(여러 세션이 공유하는 디렉토리)에 두는 바람에 번호가 세션 경계를 넘어
    계속 올라갔다(세션 2의 첫 커밋이 `call 47`). 데이터는 멀쩡했고 이름표만
    틀렸지만, 그 이름표를 믿은 분석은 통째로 어긋난다.
    """
    counter = state_dir / "call-count.txt"
    try:
        value = int(counter.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        value = 0
    value += 1
    counter.write_text(str(value), encoding="utf-8")
    return value


def take(workdir: Path) -> str | None:
    """한 번 스냅숏한다. 바뀐 것이 없으면 커밋하지 않는다.

    돌려주는 값은 커밋 해시, 또는 찍을 것이 없었으면 None.
    """
    config = _load_config(workdir)
    if not config:
        return None
    git_dir = Path(config["git_dir"])
    state_dir = Path(config.get("state_dir", git_dir.parent))
    index = _next_index(state_dir)

    _git(git_dir, workdir, "add", "-A")
    done = _git(git_dir, workdir, "-c", "user.name=casa",
                "-c", "user.email=casa@local",
                "commit", "-q", "-m", f"call {index}")
    if done.returncode != 0:
        return None                      # 바뀐 것이 없다
    head = _git(git_dir, workdir, "rev-parse", "HEAD")
    return head.stdout.strip() or None


def main() -> int:
    try:
        sys.stdin.read()                 # 훅 입력은 읽고 버린다
        workdir = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd())
        take(workdir)
    except Exception:                    # noqa: BLE001 - 관측이 세션을 죽이면 안 된다
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
