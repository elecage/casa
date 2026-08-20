"""이미 모은 세션에서 함정이 실제로 얼마나 나오는가 (과제별).

무대를 짓기 전에 **함정 밀도의 기준선**을 실측으로 잡는다. 무대에 함정을
몇 개 심을지를 추측으로 정하면, 나중에 "무대에서만 나오는 인공물"과
"실제로도 나오는 병리"를 구분할 수 없다.

계산되는 것은 라벨이 아니라 대리 지표다. 한계는 `src/casa/traps.py` 첫머리.

---

## 돌리기 전에 적는 예측 (사후 선택 방지)

친숙도 가설: **에이전트가 많이 만들어 본 종류의 과제일수록 바보짓이 덜
나온다.** 이 가설이 맞다면 기존 데이터에서 다음이 관측돼야 한다.

1. 흔한 과제 셋(buggy-pipeline·plugin-add·rename-sweep)의 함정 발생률이
   orbit-propagator보다 **낮다.**
2. 그 차이가 결과(성공률)뿐 아니라 **과정 지표에서도** 나타난다. 결과에서만
   갈리고 과정에서 같다면 친숙도는 난이도의 다른 이름일 뿐이다.
3. 조건 사이에 발생률이 **0과 1로 갈리지 않는다.** 모든 조건에서 0이면
   대리 지표가 무신호라는 뜻이고, 모든 조건에서 1이면 문턱이 틀린 것이다.

**실패 기준**: 1이 빗나가면 친숙도 가설은 이 데이터로 지지되지 않는다.
3이 빗나가면 문턱과 지표부터 고치고 다시 본다. 어느 쪽이든 **결과를 보고
예측을 고쳐 쓰지 않는다.**

교란 하나를 미리 적어 둔다: orbit은 낯설기도 하지만 **어렵기도 하다.**
이 데이터로는 둘을 가를 수 없다. 그래서 여기서 나오는 것은 가설의 기각
근거는 될 수 있어도 확증은 되지 못한다.

사용:
    .venv\\Scripts\\python.exe pilot/analysis/trap_rates.py results/main/* results/main2/* results/cal/*
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from casa.traps import NOT_COMPUTABLE, retro_traps  # noqa: E402
from casa.transcript import parse  # noqa: E402

RAW_KEYS = ("longest_standstill_run", "single_file_fixation", "rework_ratio",
            "reread_ratio", "n_calls")


def load(directory: Path) -> list[dict]:
    rows: list[dict] = []
    for transcript in sorted(directory.glob("transcript-*.jsonl")):
        number = transcript.name.split("transcript-")[1].split(".")[0]
        meta_path = directory / f"session-{number}.json"
        meta = {}
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8")) or {}
            except ValueError:
                meta = {}
        grade = meta.get("grade") or {}
        audit = meta.get("audit") or {}
        metrics = audit.get("metrics") or {}
        success = grade.get("success")
        if success is None:
            continue

        session = parse(transcript)
        result = retro_traps(
            session,
            success=bool(success),
            claimed=bool(metrics.get("claims_completion")),
            violations=len(audit.get("violations") or []),
        )
        rows.append({
            "condition": directory.name,
            "group": directory.parent.name,
            "session": number,
            "success": bool(success),
            **{f"flag:{k}": v for k, v in result["flags"].items()},
            **{f"raw:{k}": result["raw"][k] for k in RAW_KEYS},
        })
    return rows


def rate(rows: list[dict], key: str) -> float:
    values = [r[key] for r in rows if key in r]
    return sum(1 for v in values if v) / len(values) if values else float("nan")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+", type=Path)
    args = ap.parse_args()

    rows: list[dict] = []
    for directory in args.dirs:
        if directory.is_dir():
            rows.extend(load(directory))
    if not rows:
        print("채점된 세션을 찾지 못했다.")
        return 1

    flag_keys = sorted({k for r in rows for k in r if k.startswith("flag:")})
    conditions = sorted({r["condition"] for r in rows})

    print(f"세션 {len(rows)}건, 조건 {len(conditions)}개\n")

    head = ["조건", "n", "중앙호출", "성공률"] + [
        k.split(":", 1)[1] for k in flag_keys]
    widths = [max(len(head[0]), *(len(c) for c in conditions)), 4, 8, 6] + \
             [max(10, len(h)) for h in head[4:]]
    print("  ".join(h.ljust(w) for h, w in zip(head, widths)))
    print("  ".join("-" * w for w in widths))

    for condition in conditions:
        sub = [r for r in rows if r["condition"] == condition]
        median_calls = statistics.median([r["raw:n_calls"] for r in sub])
        cells = [condition.ljust(widths[0]),
                 str(len(sub)).ljust(widths[1]),
                 f"{median_calls:.0f}".ljust(widths[2]),
                 f"{sum(1 for r in sub if r['success']) / len(sub):.2f}".ljust(widths[3])]
        for key, width in zip(flag_keys, widths[4:]):
            cells.append(f"{rate(sub, key):.2f}".ljust(width))
        print("  ".join(cells))

    print("\n전체")
    for key in flag_keys:
        print(f"  {key.split(':', 1)[1]:<16} {rate(rows, key):.3f}")

    print("\n원자료 분포 (중앙값 / 최댓값) — 문턱이 잠정이므로 함께 낸다")
    for key in RAW_KEYS:
        values = [r[f"raw:{key}"] for r in rows]
        print(f"  {key:<24} {statistics.median(values):>8.3f}  "
              f"{max(values):>8.3f}")

    print("\n길이별 (탐색적 — 사전 등록 안 됨)")
    print("  바보짓을 하려면 그럴 자리가 있어야 한다. 짧은 세션에서 함정이")
    print("  안 나오는 것은 '안 한다'가 아니라 '할 틈이 없다'일 수 있다.")
    buckets = [("호출 1~15", 1, 15), ("호출 16~40", 16, 40),
               ("호출 41~", 41, 10 ** 9)]
    head = ["구간", "n"] + [k.split(":", 1)[1] for k in flag_keys]
    widths = [12, 4] + [max(10, len(h)) for h in head[2:]]
    print("  " + "  ".join(h.ljust(w) for h, w in zip(head, widths)))
    for label, low, high in buckets:
        sub = [r for r in rows if low <= r["raw:n_calls"] <= high]
        if not sub:
            continue
        cells = [label.ljust(widths[0]), str(len(sub)).ljust(widths[1])]
        for key, width in zip(flag_keys, widths[2:]):
            cells.append(f"{rate(sub, key):.2f}".ljust(width))
        print("  " + "  ".join(cells))
        top = Counter(r["condition"] for r in sub).most_common(3)
        print("      어느 조건에서 왔나: "
              + ", ".join(f"{c} {n}" for c, n in top))

    print("\n소급 계산 불가 — '안 나왔다'가 아니라 '못 쟀다'이다")
    for name, reason in NOT_COMPUTABLE.items():
        print(f"  {name}\n      {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
