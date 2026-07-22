#!/bin/sh
# Cross-platform hook launcher: runs hooks/<name>.py with the project venv
# python (Windows: .venv/Scripts/python.exe, POSIX: .venv/bin/python).
# Claude Code executes hook commands under Git Bash on Windows, so this
# single script serves both platforms.
dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if [ -x "$dir/../.venv/Scripts/python.exe" ]; then
  py="$dir/../.venv/Scripts/python.exe"
else
  py="$dir/../.venv/bin/python"
fi
exec "$py" "$dir/$1.py"
