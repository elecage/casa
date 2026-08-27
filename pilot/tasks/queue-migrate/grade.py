#!/usr/bin/env python3
"""`queue-migrate` 채점기 진입점. 판정은 pilot/queue_grade.py 에 있다.

이 파일은 pilot/queue_template.py 가 만든다. 손으로 고치지 말 것.
"""

import json
import sys
from pathlib import Path


def _pilot() -> Path:
    """`queue_grade.py` 가 있는 디렉토리. 위로 훑어 찾는다."""
    here = Path(__file__).resolve()
    hint = None
    for parent in [*here.parents, *([Path(hint)] if hint else [])]:
        for candidate in (parent, parent / "pilot"):
            if (candidate / "queue_grade.py").is_file():
                return candidate
    raise SystemExit("queue_grade.py 를 찾지 못했다")


sys.path.insert(0, str(_pilot()))

from queue_grade import grade  # noqa: E402

TASK = "queue-migrate"


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "사용: grade.py <작업 디렉토리>"}))
        return 1
    print(json.dumps(grade(TASK, Path(sys.argv[1]))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
