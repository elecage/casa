#!/bin/sh
# 세션 하네스 훅 런처. hooks/run.sh와 같은 패턴 — 프로젝트 venv의 python으로
# harness/<name>.py를 실행한다. 클로드 코드는 윈도우에서도 훅 명령을 Git Bash
# 로 실행하므로 이 스크립트 하나가 양쪽 플랫폼을 다 담당한다.
dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if [ -x "$dir/../.venv/Scripts/python.exe" ]; then
  py="$dir/../.venv/Scripts/python.exe"
else
  py="$dir/../.venv/bin/python"
fi
exec "$py" "$dir/$1.py"
