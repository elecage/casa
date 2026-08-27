#!/usr/bin/env python3
"""`queue-migrate` 채점기 진입점. 판정은 pilot/queue_grade.py 에 있다.

이 파일은 pilot/queue_template.py 가 만든다. 손으로 고치지 말 것.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

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
