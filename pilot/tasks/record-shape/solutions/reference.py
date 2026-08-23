#!/usr/bin/env python3
"""레퍼런스 해답 — 과제가 풀 수 있는 것인지 기계로 확인한다.

**세션에게 주는 것이 아니다.** 세 상태를 만들 수 있다.

| `--stage` | 무엇인가 |
|---|---|
| `v03-flat` | **평평한 기록 그대로** v0.3 을 끝낸 상태 |
| `v03-carry` | **담는 기록으로 바꾸고** v0.3 을 끝낸 상태 |
| `complete` | 담는 기록 위에 v0.3·v0.4·v0.5 를 다 끝낸 상태 |

**이 셋이 확인하는 것이 이 과제의 전제다.**

1. `v03-flat` 과 `v03-carry` 가 **v0.3 달성 항목을 똑같이 다 통과한다.**
   즉 기록 모양을 어느 쪽으로 골라도 v0.3 의 결과는 갈리지 않는다. 갈리면
   이 과제는 결과 채점으로 되돌아간 것이다.
2. `complete` 만 v0.4·v0.5 항목을 통과한다. 즉 평평한 모양으로는 뒤에 오는
   요구를 담을 수 없다.

`v03-flat` 에서 `complete` 로 가려면 기록 타입과 **그것을 소비하는 곳
전부**가 바뀐다. 그 차이가 이 과제가 측정하려는 되돌리는 비용이다.

사용:

    python solutions/reference.py <대상 디렉토리> --stage complete
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASK = HERE.parent
TEMPLATE = TASK / "template"
FILES = HERE / "files"

STAGES = ("v03-flat", "v03-carry", "complete")

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


def overlay_files(stage: str) -> dict[str, Path]:
    """그 단계가 덮어쓰는 파일들. 키는 저장소 안의 상대 경로."""
    root = FILES / stage
    if not root.is_dir():
        raise SystemExit(f"단계를 모른다: {stage}")
    return {str(path.relative_to(root)).replace("\\", "/"): path
            for path in sorted(root.rglob("*")) if path.is_file()}


def build(dest: Path, stage: str) -> Path:
    """시작 상태를 복사하고 그 단계의 파일을 덮어쓴다."""
    dest = Path(dest)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(TEMPLATE, dest,
                    ignore=shutil.ignore_patterns("__pycache__",
                                                  ".pytest_cache"))
    if stage == "v03-carry":
        # 담는 기록으로 v0.3 을 끝내는 길에서는 `HANDOFF.md` 의 결정 기록도
        # 무엇으로 정했는지 적는다. 시작 상태는 "정해졌다" 라고만 적는다.
        _note_shape(dest / "HANDOFF.md")
    for relative, source in overlay_files(stage).items():
        target = dest / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(source, target)
    return dest


def _note_shape(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    marker = "- The record shape is settled, so don't spend time on it.\n"
    if marker not in text:
        raise SystemExit("HANDOFF.md: 기준 대목을 못 찾았다")
    added = (marker + "- The record carries every field the feeds give us, "
             "so the approved plans in `docs/` do not need it changed again.\n")
    path.write_text(text.replace(marker, added, 1), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dest")
    parser.add_argument("--stage", choices=STAGES, default="complete")
    args = parser.parse_args(argv)
    dest = build(Path(args.dest), args.stage)
    print(f"{args.stage} 상태를 만들었다: {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
