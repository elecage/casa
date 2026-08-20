#!/usr/bin/env python3
"""사슬 배치 평가 — 세션마다 함정 상태 벡터를 내고, 봉인된 규칙대로 초반 신호를
고른다.

`probe_eval.py`는 단발 배치용이라 사슬에 그대로 못 쓴다. 다른 점 둘:

1. **스냅숏 저장소가 사슬마다 하나다.** 세 세션이 한 작업 디렉토리를 물려받으니
   커밋도 한 줄로 이어진다. 세션 경계는 각 세션이 파일을 바꾼 호출 수만큼
   앞에서부터 잘라 나눈다.
2. **뒤 세션의 시작 상태는 과제 템플릿이 아니다.** 앞 세션이 남긴 트리에서
   시작한다. 그 상태를 시작 조건으로 넣지 않으면 물려받은 함정을 "이 세션이
   빠뜨렸다"고 잘못 적는다.

신호 고르기 규칙은 `docs/EARLY_DETECTION_PROTOCOL.md` 4절에 돌리기 전에
봉인돼 있다. 이 파일은 그것을 그대로 계산할 뿐이다 — 자격은 "세 판정 시점 중
두 곳 이상에서 같은 방향", 고르기는 "갈라진 폭이 큰 순서로 셋".

사용:

    .venv/bin/python pilot/analysis/chain_eval.py results/chain3/release-traps
"""

from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import statistics
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from casa.transcript import Session, parse  # noqa: E402
from casa.trap_state import ENDED_IN_TRAP, RECOVERED  # noqa: E402
from casa.signals import compute_signals  # noqa: E402

#: 판정 시점. 봉인 문서 4절.
CHECKPOINTS = (10, 20, 30)


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


probe = _load("chain_eval_probe", ROOT / "pilot" / "analysis" / "probe_eval.py")


# ------------------------------------------------------------- 세션 읽기

def load_chain_sessions(out_dir: Path) -> list[dict]:
    """(사슬 번호, 이름표, 세션) 목록. 사슬·순서대로."""
    rows = []
    for path in sorted(glob.glob(str(out_dir / "session-*.json"))):
        meta = json.loads(Path(path).read_text(encoding="utf-8"))
        transcript = meta.get("transcript")
        rows.append({
            "chain": meta.get("chain"),
            "label": meta.get("label"),
            "meta": meta,
            "session": parse(Path(transcript)) if transcript else None,
        })
    return rows


def segments(sessions, commits: list[str]) -> list[list[str]]:
    """사슬의 커밋 한 줄을 세션별로 나눈다.

    세션이 파일을 바꾼 호출 수만큼 앞에서부터 가져간다. 커밋 제목의 번호에
    기대지 않는다 — 번호는 틀린 적이 있고 순서는 틀린 적이 없다.
    """
    out, cursor = [], 0
    for session in sessions:
        n = len(probe.changed_call_indices(session))
        out.append(commits[cursor:cursor + n])
        cursor += n
    return out


def trap_vectors(out_dir: Path, task_dir: Path) -> dict[str, dict]:
    """세션 이름표 → 함정 상태 벡터."""
    start = probe.detect.tree_conditions(
        task_dir / "template", probe.grade.checkpoints(task_dir / "template"))
    rows = load_chain_sessions(out_dir)
    vectors: dict[str, dict] = {}

    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        for chain in sorted({r["chain"] for r in rows}):
            mine = [r for r in rows if r["chain"] == chain and r["session"]]
            git_dir = (out_dir / "snapshots" / f"chain-{chain:02d}.git").resolve()
            commits = [c for _no, c in probe.snapshot_calls(git_dir)]
            inherited = start
            for row, seg in zip(mine, segments([r["session"] for r in mine], commits)):
                session = row["session"]
                pairs = dict(zip(probe.changed_call_indices(session), seg))
                series, current, cache = [], inherited, {}
                for index in range(len(session.tool_calls)):
                    commit = pairs.get(index)
                    if commit is not None:
                        if commit not in cache:
                            cache[commit] = probe.conditions_at(git_dir, commit, tmp)
                        current = cache[commit]
                    series.append(current)
                checks = (row["meta"].get("grade") or {}).get("checkpoints") or {}
                vectors[row["label"]] = probe.detect.outcomes(
                    session, series, start_conditions=inherited,
                    checkpoints=checks)
                inherited = current          # 다음 세션이 물려받는 상태
    return vectors


def blame_counts(vectors: dict[str, dict]) -> dict[str, dict[str, int]]:
    """세션마다 잘못을 갈라 센다 — 만든 것, 물려받아 못 고친 것, 고친 것."""
    out = {}
    for label, vector in vectors.items():
        tally = {"made": 0, "inherited": 0, "fixed": 0, "recovered": 0}
        for outcome in vector.values():
            if outcome.blame in tally:
                tally[outcome.blame] += 1
        out[label] = tally
    return out


def ended_in_trap_counts(vectors: dict[str, dict]) -> dict[str, int]:
    """**이 세션이 만든** 함정 수. 물려받아 못 고친 것은 여기 안 센다.

    2026-08-20 보정에서 앞 세션이 남긴 가짜 산출을 물려받은 뒤 세션 둘이
    "빠진 채 종료"로 기록됐다. 자기가 만들지도 않은 것이다.
    """
    return {label: sum(1 for outcome in vector.values()
                       if outcome.blame == "made")
            for label, vector in vectors.items()}


def bad_sessions(counts: dict[str, int]) -> tuple[set[str], float]:
    """나쁜 세션 = **이 세션이 만든** 함정 수가 중앙값보다 많은 세션.

    봉인 문서 3절. 중앙값은 이 배치에서 계산한다.
    """
    median = statistics.median(counts.values()) if counts else 0.0
    return {label for label, n in counts.items() if n > median}, median


# --------------------------------------------------------------- 신호 고르기

def _head(session: Session, k: int) -> Session:
    head = Session(path=session.path)
    head.tool_calls = session.tool_calls[:k]
    head.final_assistant_text = None       # 초반 판정에 마지막 보고는 못 쓴다
    return head


def signal_table(sessions: dict[str, Session], bad: set[str]) -> dict:
    """신호 → 판정 시점 → (나쁜 무리 중앙값, 나머지 중앙값, 갈라진 폭)."""
    table: dict[str, dict] = {}
    for k in CHECKPOINTS:
        groups: dict[str, dict[str, list]] = {}
        for label, session in sessions.items():
            if len(session.tool_calls) < k:
                continue                    # 그 시점의 판정 대상이 아니다
            for key, value in compute_signals(_head(session, k)).items():
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    continue                # 참거짓·글자는 초반 판정에 안 쓴다
                side = "bad" if label in bad else "ok"
                groups.setdefault(key, {"bad": [], "ok": []})[side].append(value)
        for key, group in groups.items():
            if len(group["bad"]) < 3 or len(group["ok"]) < 3:
                continue                    # 한쪽이 너무 적으면 견줄 수 없다
            median_bad = statistics.median(group["bad"])
            median_ok = statistics.median(group["ok"])
            values = group["bad"] + group["ok"]
            span = (max(values) - min(values)) or 1
            table.setdefault(key, {})[k] = (
                median_bad, median_ok, (median_bad - median_ok) / span)
    return table


def choose(table: dict, limit: int = 3) -> list[tuple[float, str, int, dict]]:
    """봉인된 고르기 규칙.

    자격: 세 시점 중 **두 곳 이상에서 같은 방향**으로 갈린다.
    고르기: 갈라진 폭(중앙값 차이를 범위로 나눈 값)이 큰 순서로 셋까지.
    """
    ranked = []
    for key, per_k in table.items():
        for sign in (1, -1):
            widths = [abs(d) for _b, _o, d in per_k.values()
                      if (d > 0) == (sign > 0) and d != 0]
            if len(widths) >= 2:
                ranked.append((statistics.mean(widths), key, sign, per_k))
                break
    ranked.sort(key=lambda row: (-row[0], row[1]))
    return ranked[:limit]


# ------------------------------------------------------------------- 출력

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--task", type=Path,
                    default=ROOT / "pilot" / "tasks" / "release-traps")
    args = ap.parse_args()

    rows = load_chain_sessions(args.out_dir)
    if not rows:
        print("세션을 찾지 못했다.")
        return 1

    vectors = trap_vectors(args.out_dir, args.task)
    counts = ended_in_trap_counts(vectors)
    bad, median = bad_sessions(counts)

    print("=== 세션마다 (세션 점수 = 함정 상태 벡터) ===")
    for row in rows:
        label = row["label"]
        vector = vectors.get(label, {})
        made = [k for k, v in vector.items() if v.blame == "made"]
        inherited = [k for k, v in vector.items() if v.blame == "inherited"]
        fixed = [k for k, v in vector.items() if v.blame == "fixed"]
        recovered = [k for k, v in vector.items() if v.blame == "recovered"]
        checks = (row["meta"].get("grade") or {}).get("checkpoints") or {}
        passed = sum(1 for v in checks.values() if v is True)
        print(f"  {label}: 만든 함정 {len(made)}개 {made or ''}"
              f" | 물려받아 못 고침 {inherited or '없음'}"
              f" | 물려받아 고침 {fixed or '없음'}"
              f" | 스스로 회복 {recovered or '없음'}"
              f" | (부수 기록: 달성 {passed}/9)")

    print(f"\n빠진 채 종료 분포 중앙값 {median} → 나쁜 세션 = 중앙값 초과")
    print(f"나쁜 세션 {len(bad)}/{len(counts)} = {len(bad)/max(1,len(counts)):.0%}:"
          f" {sorted(bad)}")

    sessions = {r["label"]: r["session"] for r in rows if r["session"]}
    table = signal_table(sessions, bad)
    picked = choose(table)
    print("\n=== 초반 신호 고르기 (봉인된 규칙) ===")
    if not picked:
        print("  자격을 얻은 신호가 없다.")
    for width, key, sign, per_k in picked:
        cells = " ".join(f"K{k}:{b:.2f}/{o:.2f}"
                         for k, (b, o, _d) in sorted(per_k.items()))
        way = "나쁜 쪽이 큼" if sign > 0 else "나쁜 쪽이 작음"
        print(f"  갈라진 폭 {width:.2f}  {key:24} {way}  {cells}")
    if len(picked) < 3:
        print(f"  → 셋을 채우지 못했다({len(picked)}개). 자격 미달 신호를 "
              f"끌어오지 않는다 (봉인 문서 4절 3번).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
