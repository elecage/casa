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
import re
import subprocess
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

CONFIG_NAME = ".casa-snapshot.json"

#: 스냅숏에서 빼는 것들. 우리가 심어 둔 설정 파일과 부산물이라 세션의
#: 작업이 아니다.
EXCLUDES = (".casa-chain.json", ".casa-snapshot.json", ".casa-queue.json",
            ".claude/", "__pycache__/", "*.pyc")


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
    # 절대 경로로 못 박는다. `_git` 은 작업 트리 **안에서** git 을 돌리므로
    # 상대 경로를 그대로 넘기면 그 안에서 다시 풀려 엉뚱한 데를 가리키고,
    # 스냅숏이 실패로도 안 보인 채 조용히 빈다. 이 영역에서 상대 경로에 속은
    # 것이 2026-08-20에만 두 번이다.
    workdir, git_dir = Path(workdir).resolve(), Path(git_dir).resolve()
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

    _baseline(workdir, git_dir)


def _baseline(workdir: Path, git_dir: Path) -> None:
    """세션이 시작하기 전 상태를 커밋 하나로 찍어 둔다.

    **왜 필요한가.** 이것이 없으면 첫 스냅숏이 뿌리 커밋이라 "이 호출이 무엇을
    바꿨나"가 **저장소 전체**로 나온다. 호출마다의 변경을 항목에 귀속하려면
    (`pilot/tasks/release-traps/attribute.py`) 견줄 앞 시점이 있어야 하고,
    없으면 세션마다 첫 호출 하나를 통째로 잃는다.

    제목을 `call N` 으로 짓지 않는다 — 호출 번호를 읽는 분석기들이 제목이
    `call ` 로 시작하는 커밋만 세므로, 이 커밋은 그 셈에 안 들어간다.
    """
    head = _git(git_dir, workdir, "rev-parse", "--verify", "HEAD")
    if head.returncode == 0:
        return                           # 이미 무언가 찍혀 있다
    _git(git_dir, workdir, "add", "-A")
    _git(git_dir, workdir, "-c", "user.name=casa", "-c", "user.email=casa@local",
         "commit", "-q", "--allow-empty", "-m", "baseline")


def _load_config(workdir: Path) -> dict | None:
    path = workdir / CONFIG_NAME
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None


def _claim(state_dir: Path, index: int) -> bool:
    """이 번호를 이 호출이 가져간다. 이미 누가 가져갔으면 거짓.

    파일 하나를 **`O_EXCL` 로** 만드는 것이 판정이다. 같은 번호를 두 호출이
    동시에 시도하면 하나만 성공한다. 잠금 장치가 따로 필요 없고 POSIX 와
    Windows 에서 같은 방식으로 동작한다.
    """
    try:
        handle = os.open(str(state_dir / f"call-{index}.claim"),
                         os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    except OSError:
        return True          # 만들 수 없는 자리면 번호라도 진행시킨다
    os.close(handle)
    return True


def _next_index(state_dir: Path, git_dir: Path) -> int:
    """이 사슬의 다음 호출 번호.

    세어 두는 것은 **스냅숏 저장소 옆**에 둔다. 사슬 하나가 저장소 하나를
    쓰므로 번호는 그 사슬의 세션들에 걸쳐 이어진다.

    **읽고-더하고-쓰기를 하지 않는다.** 그렇게 하면 도구를 병렬로 부르는
    세션에서 두 훅이 같은 값을 읽고 같은 값을 쓴다. 2026-08-21 본 배치
    사슬 4에서 실제로 일어났다 — 번호가 175에서 12로 되감기고 81·84가
    중복됐다. 커밋 자체는 멀쩡했지만 그 이름표로 세션 구간을 나누는 분석이
    통째로 어긋났다. 앞선 실수(번호를 한 칸 위 디렉토리에 두어 세션 경계를
    넘어 이어진 것)와 원인이 다르고 증상이 비슷하다.

    대신 번호마다 파일 하나를 `O_EXCL` 로 만들어 본다. 만들어지면 그 번호가
    이 호출의 것이고, 이미 있으면 다음 번호로 넘어간다. **번호가 뒤로 가는
    일이 원리적으로 없다.**
    """
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        taken = [int(p.name[5:-6]) for p in state_dir.glob("call-*.claim")
                 if p.name[5:-6].isdigit()]
    except OSError:
        taken = []
    index = max([*taken, _floor(state_dir, git_dir)], default=0)
    while True:
        index += 1
        if _claim(state_dir, index):
            return index


def _floor(state_dir: Path, git_dir: Path) -> int:
    """이미 쓰인 가장 큰 번호. 여기서부터 이어 붙인다.

    **이어 돌리기 때문에 필요하다.** 중단된 배치를 `--resume` 으로 이으면
    자리를 맡아 둔 파일이 아직 없는 사슬이 있고, 그러면 번호가 1부터 다시
    시작해 앞 세션들의 번호와 겹친다. 앞서 쓰던 세는 파일과 저장소에 이미
    찍힌 이름표를 둘 다 보고 큰 쪽을 바닥으로 삼는다.
    """
    floor = 0
    try:
        floor = int((state_dir / "call-count.txt").read_text(
            encoding="utf-8").strip())
    except (OSError, ValueError):
        pass
    try:
        done = subprocess.run(
            ["git", f"--git-dir={git_dir}", "log", "--format=%s"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=60)
        labels = [int(m) for m in re.findall(r"^call (\d+)$", done.stdout,
                                             re.MULTILINE)]
        floor = max([floor, *labels], default=floor)
    except (OSError, subprocess.SubprocessError):
        pass
    return floor


def take(workdir: Path) -> str | None:
    """한 번 스냅숏한다. 바뀐 것이 없으면 커밋하지 않는다.

    돌려주는 값은 커밋 해시, 또는 찍을 것이 없었으면 None.
    """
    workdir = Path(workdir).resolve()
    config = _load_config(workdir)
    if not config:
        return None
    git_dir = Path(config["git_dir"]).resolve()
    state_dir = Path(config.get("state_dir", git_dir.parent)).resolve()
    index = _next_index(state_dir, git_dir)

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
