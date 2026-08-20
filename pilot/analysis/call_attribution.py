#!/usr/bin/env python3
"""호출을 릴리스 항목에 귀속해 쏠림 창·비율을 도출하고, 저장소에 일이 몇
세션 분량 남아 있는지 잰다.

두 가지를 낸다. 둘 다 2026-08-20 유저 결정에 딸린 것이다.

1. **쏠림 창과 비율** — 귀속 방법이 없어 `docs/PROBE_RESULTS.md` 3절에서
   "도출 불가"로 남고 하한(10 / 0.5)을 쓰던 자리다. 귀속은 **바꾼 파일**로
   한다(`pilot/tasks/release-traps/attribute.py`).
2. **세션이 새로 채운 달성 항목 수** — 사슬을 몇 세션으로 잡을지, 손댈 자리를
   더 늘릴지를 이 숫자로 정한다. 프로브는 "완주 0/6"만 적었고 **몇 개까지
   갔는지**는 안 적었다.

**달성 항목 수는 세션 점수가 아니다.** 저장소에 일이 얼마나 들었는지 재는
눈금이고, 그 눈금은 **과제 크기를 정하는 데만** 쓴다. 세션 점수는 함정 상태
벡터다(`docs/RECOVERY_RULE.md`, `pilot/analysis/probe_eval.py`). 이 숫자를
점수 자리에 올리면 이름만 바꾼 결과 채점이 된다 — 이 프로젝트가 2026-08-20에
한 번 그렇게 했다가 반려됐다.

사용:

    .venv/bin/python pilot/analysis/call_attribution.py results/probe/release-traps

수집이 아니라 분석이다 — 잠금과 무관하게 돌릴 수 있다.

**한 가지 한계를 먼저 적는다.** 2026-08-20 프로브 데이터에는 시작 상태
커밋이 없다(`pilot/snapshot.py` 의 baseline 은 그 뒤에 넣었다). 그 데이터에서는
**세션마다 첫 스냅숏이 저장소 전체로 나오므로 귀속에서 뺀다.** 출력에 몇 개를
뺐는지 적는다.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

TASK = ROOT / "pilot" / "tasks" / "release-traps"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


attribute = _load("release_traps_attribute", TASK / "attribute.py")


# --------------------------------------------------------------- 스냅숏 읽기

def _git(git_dir: Path, *args: str) -> str:
    done = subprocess.run(["git", f"--git-dir={git_dir}", *args],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace")
    return done.stdout if done.returncode == 0 else ""


def call_commits(git_dir: Path) -> list[tuple[int, str]]:
    """(호출 번호, 커밋). 오래된 것부터. 시작 상태 커밋은 제목이 달라 빠진다."""
    out = []
    for line in _git(git_dir, "log", "--reverse", "--format=%H %s").splitlines():
        commit, _, subject = line.partition(" ")
        if subject.startswith("call "):
            try:
                out.append((int(subject.split()[1]), commit))
            except (IndexError, ValueError):
                continue
    return out


def changed_paths(git_dir: Path, commit: str) -> list[str] | None:
    """그 커밋이 바꾼 파일들. 앞 시점이 없으면(뿌리 커밋) None."""
    parents = _git(git_dir, "rev-list", "--parents", "-n", "1", commit).split()
    if len(parents) < 2:
        return None                      # 견줄 앞 시점이 없다
    return _git(git_dir, "diff", "--name-only", f"{commit}~1", commit).split()


def load(out_dir: Path) -> list[dict]:
    rows = []
    for meta_path in sorted(out_dir.glob("session-*.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        index = meta.get("session_index")
        rows.append({
            "index": index,
            "meta": meta,
            "git_dir": (out_dir / "snapshots" / f"work-{index:02d}.git").resolve(),
        })
    return rows


def session_changes(git_dir: Path) -> tuple[list[list[str]], int]:
    """세션 하나의 호출별 변경 파일 목록과, 견줄 데가 없어 뺀 호출 수."""
    changes, dropped = [], 0
    for _no, commit in call_commits(git_dir):
        paths = changed_paths(git_dir, commit)
        if paths is None:
            dropped += 1
            continue
        changes.append(paths)
    return changes, dropped


# ------------------------------------------------------------------- 출력

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir", type=Path)
    args = ap.parse_args()

    rows = load(args.out_dir)
    if not rows:
        print("세션을 찾지 못했다.")
        return 1

    sessions, dropped_total, achieved = [], 0, []
    print("=== 세션마다 === (달성 항목은 크기를 재는 눈금이지 세션 점수가 아니다)")
    for row in rows:
        changes, dropped = session_changes(row["git_dir"])
        dropped_total += dropped
        marks = attribute.attribute_session(changes)
        sessions.append(marks)

        checks = (row["meta"].get("grade") or {}).get("checkpoints") or {}
        new = attribute.newly_achieved(checks) if checks else 0
        achieved.append(new)
        left = sorted(name for name, value in checks.items() if value is not True)

        counts = attribute.per_item_counts(marks)
        named = ", ".join(f"{attribute.ITEMS[k].split('.')[0]}번 {v}호출"
                          for k, v in sorted(counts.items(),
                                             key=lambda kv: -kv[1]))
        print(f"  세션 {row['index']}: 새로 채운 달성 항목 {new}개"
              f" | 못 채운 항목 {left or '없음'}")
        print(f"      귀속 {named or '없음'}"
              f" | 미귀속 {sum(1 for m in marks if m is None)}호출")

    print("\n=== 쏠림 창·비율 도출 (귀속 = 바꾼 파일) ===")
    derived = attribute.derive(sessions)
    print(f"  항목 하나에 쓴 호출 수의 중앙값: {derived['window_seen']}")
    print(f"  창 확정: {derived['window_final']}"
          f" (하한 {attribute.FLOORS['window']})")
    print(f"  창 안 한 항목 집중도의 90번째 백분위수: {derived['share_seen']}")
    print(f"  비율 확정: {derived['share_final']}"
          f" (하한 {attribute.FLOORS['share']})")
    print(f"  귀속 {derived['attributed']}호출 / 미귀속 {derived['unattributed']}호출")
    if dropped_total:
        print(f"  견줄 앞 시점이 없어 뺀 호출: {dropped_total}"
              f" (시작 상태 커밋이 없던 시절 데이터)")

    print("\n=== 저장소에 일이 몇 세션 분량 있나 ===")
    worth = attribute.sessions_worth_of_work(achieved, total_items=8)
    print(f"  세션마다 새로 채운 항목: {achieved}")
    print(f"  전체 8개(시작부터 참인 하나 제외) 기준 대략 {worth}세션 분량"
          f" — **외삽이다.** 사슬은 물려받은 상태가 있어 달라진다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
