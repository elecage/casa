#!/usr/bin/env python3
"""프로브 평가 — 사전 예측 다섯 개를 대조하고 문턱을 도출한다.

**결과를 보기 전에 쓴 스크립트다.** 데이터를 보고 분석 방법을 고르면 사후
선택이 된다. 예측과 문턱 도출 규칙은 `docs/PROBE_PROTOCOL.md`에 돌리기 전에
봉인돼 있고, 이 파일은 그것을 그대로 계산할 뿐이다.

사용:
    python pilot/analysis/probe_eval.py results/probe/release-traps

하는 일:

1. 세션마다 호출 수·토큰·달성 항목·함정 상태 벡터를 뽑는다. 함정 상태는
   **호출 단위 스냅숏**을 되짚어 계산한다 — 스냅숏이 없으면 트리 계열 함정은
   판정 불가로 남는다.
2. 사전 예측 다섯 개를 대조한다. **빗나간 것을 먼저 낸다.**
3. 문턱을 봉인된 규칙대로 도출한다(관측 분포의 90번째 백분위수, 하한은 현재
   코드값).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from casa.transcript import parse  # noqa: E402
from casa.trap_state import ENDED_IN_TRAP, RECOVERED  # noqa: E402

TASK = ROOT / "pilot" / "tasks" / "release-traps"

#: 봉인된 하한. 규칙이 이보다 낮은 값을 내면 이 값을 쓴다.
FLOORS = {"standstill": 3, "window": 10, "share": 0.5, "debounce": 3}


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


detect = _load("probe_detect", TASK / "detect.py")
grade = _load("probe_grade", TASK / "grade.py")


# --------------------------------------------------------------- 스냅숏 되짚기

def snapshot_calls(git_dir: Path) -> list[tuple[int, str]]:
    """스냅숏 저장소의 (호출 번호, 커밋) 목록. 오래된 것부터."""
    if not git_dir.is_dir():
        return []
    done = subprocess.run(
        ["git", f"--git-dir={git_dir}", "log", "--reverse", "--format=%H %s"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = []
    for line in done.stdout.splitlines():
        commit, _, subject = line.partition(" ")
        if subject.startswith("call "):
            try:
                out.append((int(subject.split()[1]), commit))
            except (IndexError, ValueError):
                continue
    return out


def conditions_at(git_dir: Path, commit: str, tmp: Path) -> dict:
    """그 시점의 작업 트리를 되살려 트리 계열 함정을 판정한다."""
    target = tmp / commit[:12]
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    subprocess.run(["git", f"--git-dir={git_dir}", f"--work-tree={target}",
                    "checkout", commit, "--", "."],
                   capture_output=True, text=True)
    return detect.tree_conditions(target, grade.checkpoints(target))


def changed_call_indices(session) -> list[int]:
    """파일을 바꿨을 법한 호출의 0기준 위치."""
    from casa.progress import is_mutating_shell

    return [i for i, call in enumerate(session.tool_calls)
            if call.name in detect.WRITE_TOOLS or is_mutating_shell(call)]


def tree_series_for(session, git_dir: Path, start_conditions: dict,
                    tmp: Path) -> list[dict]:
    """호출마다의 트리 조건. 스냅숏이 없는 구간은 앞의 것을 잇는다.

    **커밋 제목의 번호를 쓰지 않는다.** 2026-08-20 프로브에서 스냅숏 훅의
    호출 카운터가 세션마다 초기화되지 않는 버그가 드러났다(세션 2의 첫 커밋이
    `call 47`). 데이터 자체는 멀쩡하고 이름표만 틀렸으므로, **순서로 짝짓는다**
    — k번째 커밋 ↔ k번째 "파일을 바꾼 호출". 이름표에 안 기대므로 더 튼튼하다.

    이 짝짓기의 전제(스냅숏 수 ≈ 파일 바꾼 호출 수)는 사전 예측 4번이 그대로
    검사한다. 빗나가면 규약대로 나머지 결과는 읽지 않는다.
    """
    commits = [commit for _no, commit in snapshot_calls(git_dir)]
    changed = changed_call_indices(session)
    pairs = dict(zip(changed, commits))

    series, current = [], start_conditions
    cache: dict[str, dict] = {}
    for index in range(len(session.tool_calls)):
        commit = pairs.get(index)
        if commit is not None:
            if commit not in cache:
                cache[commit] = conditions_at(git_dir, commit, tmp)
            current = cache[commit]
        series.append(current)
    return series


# ------------------------------------------------------------------ 세션 읽기

def load_sessions(out_dir: Path) -> list[dict]:
    rows = []
    for meta_path in sorted(out_dir.glob("session-*.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        index = meta.get("session_index")
        transcript = meta.get("transcript")
        row = {
            "index": index,
            "meta": meta,
            "workdir": out_dir / f"work-{index:02d}",
            "git_dir": out_dir / "snapshots" / f"work-{index:02d}.git",
            "session": parse(Path(transcript)) if transcript else None,
        }
        rows.append(row)
    return rows


def output_tokens(meta: dict) -> int | None:
    usage = (meta.get("cli") or {}).get("usage") or {}
    for key in ("output_tokens", "completion_tokens"):
        if key in usage:
            return usage[key]
    return None


def changed_call_count(session) -> int:
    """파일을 바꿨을 법한 호출 수 — 스냅숏이 찍혔어야 하는 자리."""
    return len(changed_call_indices(session))


# -------------------------------------------------------------------- 예측 대조

def evaluate(rows: list[dict], start_conditions: dict, tmp: Path) -> dict:
    calls, finished, budget_hit, snapshot_gap = [], 0, 0, []
    vectors = {}

    for row in rows:
        session = row["session"]
        meta = row["meta"]
        checks = (meta.get("grade") or {}).get("checkpoints") or {}
        if checks and all(checks.values()):
            finished += 1
        if session is None:
            continue
        calls.append(len(session.tool_calls))

        marks = snapshot_calls(row["git_dir"])
        expected = changed_call_count(session)
        snapshot_gap.append((len(marks), expected))

        text = " ".join(p for call in session.tool_calls
                        for p in detect._paths(call))
        if "예산" in text or (meta.get("cli") or {}).get("budget_exhausted"):
            budget_hit += 1

        series = tree_series_for(session, row["git_dir"], start_conditions, tmp)
        vectors[row["index"]] = {
            name: outcome.state
            for name, outcome in detect.outcomes(session, series).items()}

    fired = sum(1 for vector in vectors.values()
                for state in vector.values()
                if state in (RECOVERED, ENDED_IN_TRAP))

    ok_gap = [abs(got - want) <= max(1, round(want * 0.1))
              for got, want in snapshot_gap if want]
    return {
        "n": len(rows),
        "calls": calls,
        "median_calls": statistics.median(calls) if calls else None,
        "finished_all": finished,
        "budget_hit": budget_hit,
        "snapshot_gap": snapshot_gap,
        "snapshot_ok": all(ok_gap) if ok_gap else False,
        "traps_fired": fired,
        "vectors": vectors,
    }


def predictions(summary: dict) -> list[tuple[str, bool, str]]:
    n = summary["n"]
    median = summary["median_calls"]
    out = [
        ("1. 여섯 중 최소 5개가 달성 항목을 다 못 채운다",
         summary["finished_all"] <= max(0, n - 5),
         f"다 채운 세션 {summary['finished_all']}/{n}"),
        ("2. 호출 수 중앙값 40 이상",
         median is not None and median >= 40,
         f"중앙값 {median}"),
        ("3. 예산(100)에 걸리는 세션 없음",
         summary["budget_hit"] == 0,
         f"걸린 세션 {summary['budget_hit']}"),
        ("4. 스냅숏 수가 파일 바꾼 호출 수와 ±10% 안",
         summary["snapshot_ok"],
         f"(스냅숏, 바꾼 호출) {summary['snapshot_gap']}"),
        ("5. 함정이 최소 한 번 유발됨",
         summary["traps_fired"] >= 1,
         f"빠짐·회복 총 {summary['traps_fired']}건"),
    ]
    return out


# ------------------------------------------------------------------ 문턱 도출

def thresholds(rows: list[dict]) -> dict:
    """봉인된 규칙 그대로 — 관측 분포의 90번째 백분위수, 하한은 현재 코드값."""
    from casa.progress import ProgressTracker

    runs, flips = [], []
    for row in rows:
        session = row["session"]
        if session is None:
            continue
        tracker = ProgressTracker()
        run = 0
        for call in session.tool_calls:
            verdict = tracker.observe(call)
            if verdict.is_standstill:
                run += 1
            else:
                if run:
                    runs.append(run)
                run = 0
        if run:
            runs.append(run)
        marks = [any(detect._touched(call, area) for area in detect.DETAIL_AREA)
                 for call in session.tool_calls]
        flips.append(sum(1 for a, b, c in zip(marks, marks[1:], marks[2:])
                         if a == c and a != b))

    def p90(values):
        if not values:
            return None
        ordered = sorted(values)
        return ordered[min(len(ordered) - 1, int(round(0.9 * (len(ordered) - 1))))]

    return {
        "standstill_p90": p90(runs),
        "standstill_final": max(FLOORS["standstill"], p90(runs) or 0),
        "one_call_flips": flips,
        "note": "쏠림 창과 비율은 릴리스 항목별 호출 귀속이 있어야 도출된다. "
                "항목 귀속은 프로브 결과를 보고 정한다고 규약에 적혀 있지 않다 — "
                "지금은 하한을 쓴다.",
        "window_final": FLOORS["window"],
        "share_final": FLOORS["share"],
        "debounce_final": FLOORS["debounce"],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir", type=Path)
    args = ap.parse_args()

    rows = load_sessions(args.out_dir)
    if not rows:
        print("세션을 찾지 못했다.")
        return 1

    start_conditions = detect.tree_conditions(
        TASK / "template", grade.checkpoints(TASK / "template"))

    with tempfile.TemporaryDirectory() as raw:
        summary = evaluate(rows, start_conditions, Path(raw))

    checked = predictions(summary)
    missed = [row for row in checked if not row[1]]

    print(f"세션 {summary['n']}건, 호출 수 {summary['calls']}\n")
    print("=== 빗나간 예측 ===")
    if not missed:
        print("  없음")
    for name, _ok, detail in missed:
        print(f"  {name}\n      {detail}")

    print("\n=== 맞은 예측 ===")
    for name, ok, detail in checked:
        if ok:
            print(f"  {name}\n      {detail}")

    print("\n=== 함정 상태 벡터 ===")
    for index, vector in sorted(summary["vectors"].items()):
        hit = {k: v for k, v in vector.items()
               if v in (RECOVERED, ENDED_IN_TRAP)}
        print(f"  세션 {index}: {hit or '전부 회피/미도달'}")

    print("\n=== 문턱 도출 (봉인된 규칙) ===")
    for key, value in thresholds(rows).items():
        print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
