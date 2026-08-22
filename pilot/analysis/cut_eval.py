"""끊는 배치의 1차 지표 — **깃발이 선 자리마다** 얼마를 얻었는가.

**왜 사슬 끝 상태를 1차 지표로 쓰지 않는가.** 사슬 하나가 한 관측이면 두
갈래를 합쳐 열여섯 관측이고, 본 배치에서 사슬 끝 상태의 표준편차는 4.8이었다.
끊기가 만드는 차이의 예상 크기는 사슬 하나당 0.6항목이다. 그 크기를 그
표준편차로 판정하려면 사슬이 수백 개 필요하다 — 즉 이 설계로는 답이 안 나온다.

**그래서 관측 단위를 깃발이 선 자리로 바꾼다.** 초반 신호가 켜진 세션 하나가
한 관측이다. 본 배치에서 70세션 중 16개가 켜졌으므로, 같은 규모의 배치에서
갈래마다 열몇 개의 관측이 나온다. 사슬 여덟 개가 아니라.

**무엇을 견주는가.** 신호가 켜진 자리에서

- 안 끊는 쪽은 그 세션을 끝까지 돌리고 그 세션이 올린 만큼을 얻는다.
- 끊는 쪽은 열 호출을 버리고 새 세션을 들이고 **그 새 세션이** 올린 만큼을
  얻는다.

쓴 호출 수가 다르므로 **호출당 성과**로 견준다. 그래야 "열 호출을 버린 값이
얼마인가"가 셈에 들어간다.

**교체된 세션이 무엇을 했는지는 평균이 아니라 분포로 적는다**(2026-08-22 유저
지적). 끊는다고 더 나은 세션이 들어온다는 보장이 없다 — 더 나쁠 수도 같을
수도 있다. 평균만 적으면 그 사실이 안 보인다. 교체 세션의 성과를 정렬해서 다
적고, 안 끊는 쪽 분포보다 낮은 것·같은 것·높은 것을 각각 센다.

사용:

    python pilot/analysis/cut_eval.py --keep results/cut/keep --cut results/cut/cut
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

PILOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PILOT))

import cut_hook  # noqa: E402

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

#: 초반 몇 호출을 보고 깃발을 세우는가. 끊는 훅과 같은 수여야 한다.
DEFAULT_AT = 10


def passed(row: dict) -> int | None:
    """그 세션이 끝났을 때 통과한 달성 항목 수. 채점을 못 읽으면 None."""
    grade = row.get("grade")
    if not isinstance(grade, dict):
        return None
    checks = grade.get("checkpoints")
    if not isinstance(checks, dict):
        return None
    return sum(1 for value in checks.values() if value is True)


def calls_of(row: dict) -> int:
    return ((row.get("audit") or {}).get("metrics") or {}).get(
        "n_tool_calls", 0)


def flagged(row: dict, at: int = DEFAULT_AT) -> bool | None:
    """초반 신호가 이 세션에서 켜졌는가.

    **끊는 쪽에서는 러너가 적어 둔 것을 그대로 쓴다** — 훅이 실제로 끊었으면
    깃발이 선 것이다. 안 끊는 쪽에는 그 기록이 없으므로 트랜스크립트에서
    같은 판정을 다시 낸다. 두 갈래가 같은 판정을 쓰지 않으면 견줄 수 없다.
    """
    if row.get("cut") is True:
        return True
    path = row.get("transcript")
    if not path or not Path(path).is_file():
        return None
    calls = cut_hook.tool_calls(Path(path))
    if len(calls) < at:
        # 신호를 낼 만큼 호출이 없었다. 못 켜진 것이 아니라 판정 불가다.
        return None
    return not cut_hook.opened_code(calls[:at])


def load_chain(out_dir: Path, chain: int) -> list[dict]:
    rows = []
    for path in sorted(Path(out_dir).glob(f"session-c{chain:02d}s*.json")):
        try:
            rows.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return rows


def load_arm(out_dir: Path) -> list[list[dict]]:
    """한 갈래의 사슬들. 사슬마다 세션 기록이 순서대로 들어 있다."""
    out_dir = Path(out_dir)
    chains = sorted({int(p.name[9:11]) for p in
                     out_dir.glob("session-c*s*.json")})
    return [load_chain(out_dir, chain) for chain in chains]


def occurrences(chain_rows: list[dict], at: int = DEFAULT_AT,
                start: int | None = None) -> list[dict]:
    """깃발이 선 자리마다 무엇을 썼고 무엇을 얻었는지.

    `start` 는 세션 1 앞의 상태(시작 상태의 통과 항목 수)다. 안 주면 세션 1의
    성과는 판정하지 않는다 — 앞 상태를 모르면 늘어난 양을 셀 수 없다.
    """
    out = []
    before = start
    for index, row in enumerate(chain_rows):
        after = passed(row)
        gain = None if before is None or after is None else after - before
        if flagged(row, at):
            out.append({
                "chain": row.get("chain"),
                "session_index": row.get("session_index", index + 1),
                "cut": bool(row.get("cut")),
                "calls": calls_of(row),
                "gain": gain,
            })
        if after is not None:
            before = after
    return out


def _with_replacements(chain_rows: list[dict], at: int, start: int | None):
    """끊긴 자리마다 **그 자리를 이어받은 세션**의 성과를 붙인다.

    끊긴 세션은 거의 언제나 0을 올린다. 끊기의 값은 그 세션이 아니라 **다음
    세션이** 무엇을 했는지에 있다.
    """
    marks = occurrences(chain_rows, at, start)
    scores = [passed(row) for row in chain_rows]
    by_index = {row.get("session_index", i + 1): i
                for i, row in enumerate(chain_rows)}
    for mark in marks:
        if not mark["cut"]:
            continue
        here = by_index.get(mark["session_index"])
        if here is None or here + 1 >= len(chain_rows):
            mark["replacement"] = None
            continue
        after = scores[here + 1]
        mine = scores[here]
        mark["replacement"] = {
            "calls": calls_of(chain_rows[here + 1]),
            "gain": None if after is None or mine is None else after - mine,
            "cut": bool(chain_rows[here + 1].get("cut")),
        }
    return marks


def per_call(gain, calls) -> float | None:
    if gain is None or not calls:
        return None
    return gain / calls


def arm_summary(chains: list[list[dict]], at: int = DEFAULT_AT,
                start: int | None = None) -> dict:
    """한 갈래에서, 깃발이 선 자리마다 호출당 얼마를 얻었는가."""
    marks: list[dict] = []
    for rows in chains:
        marks.extend(_with_replacements(rows, at, start))

    rates: list[float] = []
    gains: list[int] = []
    for mark in marks:
        got = mark.get("replacement")
        if mark["cut"]:
            if not got:
                continue
            gain = got["gain"]
            spent = mark["calls"] + got["calls"]
        else:
            gain = mark["gain"]
            spent = mark["calls"]
        rate = per_call(gain, spent)
        if rate is None:
            continue
        rates.append(rate)
        gains.append(gain)

    return {
        "occurrences": len(marks),
        "judged": len(rates),
        "gain_per_call": rates,
        "gain_per_call_median": statistics.median(rates) if rates else None,
        "gains": sorted(gains),
        "gain_median": statistics.median(gains) if gains else None,
    }


def replacement_spread(chains: list[list[dict]], keep_gains: list[int],
                       at: int = DEFAULT_AT,
                       start: int | None = None) -> dict:
    """교체된 세션이 실제로 무엇을 했는가. **평균이 아니라 분포로 적는다.**

    안 끊는 쪽에서 깃발이 선 세션들이 올린 값의 중앙값을 기준으로, 교체 세션이
    그보다 낮았는지 같았는지 높았는지 센다. 끊기가 더 나은 뽑기를 준다는 것이
    참이라면 "높다"가 많아야 하고, 그렇지 않다면 이 표가 그것을 보여 준다.
    """
    got: list[int] = []
    for rows in chains:
        for mark in _with_replacements(rows, at, start):
            if not mark["cut"]:
                continue
            entry = mark.get("replacement")
            if entry and entry["gain"] is not None:
                got.append(entry["gain"])
    got.sort()
    if not keep_gains:
        return {"replacements": got, "baseline": None}
    baseline = statistics.median(keep_gains)
    return {
        "replacements": got,
        "baseline": baseline,
        "worse": sum(1 for g in got if g < baseline),
        "same": sum(1 for g in got if g == baseline),
        "better": sum(1 for g in got if g > baseline),
    }


def report(keep_dir: Path, cut_dir: Path, at: int = DEFAULT_AT,
           start: int | None = None) -> dict:
    keep = load_arm(keep_dir)
    cut = load_arm(cut_dir)
    keep_side = arm_summary(keep, at, start)
    cut_side = arm_summary(cut, at, start)
    return {
        "at": at,
        "start_state": start,
        "keep": keep_side,
        "cut": cut_side,
        "replacement_spread": replacement_spread(
            cut, keep_side["gains"], at, start),
    }


def render(result: dict) -> str:
    lines = ["# 끊는 배치 — 깃발이 선 자리마다의 성과", ""]
    lines.append(f"신호는 초반 {result['at']}호출을 본다. "
                 f"시작 상태 통과 항목: {result['start_state']}")
    lines.append("")
    lines.append("| 갈래 | 깃발이 선 자리 | 판정된 자리 | 호출당 성과 중앙값 | 성과 중앙값 |")
    lines.append("|---|---|---|---|---|")
    for name, key in (("안 끊는 쪽", "keep"), ("끊는 쪽", "cut")):
        side = result[key]
        rate = side["gain_per_call_median"]
        lines.append(
            f"| {name} | {side['occurrences']} | {side['judged']} | "
            f"{'—' if rate is None else f'{rate:.4f}'} | "
            f"{side['gain_median']} |")

    spread = result["replacement_spread"]
    lines += ["", "## 교체된 세션이 실제로 무엇을 했는가", ""]
    lines.append("**평균이 아니라 분포로 적는다.** 끊는다고 더 나은 세션이 "
                 "들어온다는 보장이 없다.")
    lines.append("")
    lines.append(f"- 교체 세션의 성과(정렬): {spread['replacements']}")
    if spread.get("baseline") is not None:
        lines.append(f"- 안 끊는 쪽 깃발 세션의 성과 중앙값: {spread['baseline']}")
        lines.append(f"- 그보다 낮음 {spread['worse']} / 같음 {spread['same']} / "
                     f"높음 {spread['better']}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--keep", required=True, type=Path)
    ap.add_argument("--cut", required=True, type=Path)
    ap.add_argument("--at", type=int, default=DEFAULT_AT)
    ap.add_argument("--start", type=int, default=None,
                    help="시작 상태의 통과 항목 수. 안 주면 세션 1은 판정하지 않는다.")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    result = report(args.keep, args.cut, args.at, args.start)
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json
          else render(result), end="" if not args.json else "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
