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

**이 배치가 부수적으로 기록하는 것 둘**(2026-08-22 유저 지시). 1차 지표와 별개로,
안 끊는 쪽 자료만으로 앞서 관측된 결과 둘을 다시 산출한다.

- `signal_split` — 깃발이 선 세션(초반 10호출에 `.py` 파일을 한 번도 열지 않은
  세션)과 안 선 세션이 각각 몇 %나 달성 항목을 늘렸는가. 앞 배치의 33% 대
  74%가 새 자료에서도 재현되는지 판별한다. 예측 7로 봉인되어 있다.
- `gain_spread` — 세션마다 늘린 항목 수의 분포. 사슬 끝 상태가 아니라 세션
  단위다. 예측이 아니라 서술 통계다.

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


def session_rows(chain_rows: list[dict], at: int = DEFAULT_AT,
                 start: int | None = None) -> list[dict]:
    """사슬 하나의 세션마다 (깃발, 늘린 항목 수, 쓴 호출 수).

    `occurrences()` 와 달리 **깃발이 안 선 세션도 담는다.** 두 집단을 대조해야
    초반 신호가 새 자료에서도 재현되는지 판정할 수 있고(`signal_split`),
    세션마다 얼마를 늘렸는지의 분포를 산출할 수 있다(`gain_spread`).
    """
    out = []
    before = start
    for index, row in enumerate(chain_rows):
        after = passed(row)
        out.append({
            "chain": row.get("chain"),
            "session_index": row.get("session_index", index + 1),
            "flagged": flagged(row, at),
            "cut": bool(row.get("cut")),
            "gain": None if before is None or after is None else after - before,
            "calls": calls_of(row),
        })
        if after is not None:
            before = after
    return out


def signal_split(chains: list[list[dict]], at: int = DEFAULT_AT,
                 start: int | None = None) -> dict:
    """초반 신호가 구분한 두 집단이 실제로 다른가.

    **안 끊는 쪽에서만 산출한다.** 끊는 쪽은 깃발이 선 세션을 우리가 도중에
    중단시키므로 그 세션이 무엇을 할 수 있었는지가 관측되지 않는다.

    앞 배치(`docs/EARLY_SIGNAL_RESULTS.md`)에서 초반 10호출에 `.py` 를 열지 않은
    세션은 33%가, 연 세션은 74%가 달성 항목을 늘렸다. **그 수치는 무엇을
    관측할지를 70세션 전부를 보고 선택한 값이므로 낙관적이다.** 여기서 다시
    산출하는 것이 그 신호가 새 자료에서도 재현되는지 판별하는 유일한 방법이다.
    """
    groups: dict[str, list[int]] = {"flagged": [], "unflagged": []}
    for rows in chains:
        for row in session_rows(rows, at, start):
            if row["gain"] is None or row["flagged"] is None:
                continue
            groups["flagged" if row["flagged"] else "unflagged"].append(
                row["gain"])

    out: dict[str, dict] = {}
    for key, gains in groups.items():
        raised = sum(1 for gain in gains if gain > 0)
        out[key] = {
            "n": len(gains),
            "raised": raised,
            "rate": raised / len(gains) if gains else None,
            "gains": sorted(gains),
        }
    return out


def gain_spread(chains: list[list[dict]], at: int = DEFAULT_AT,
                start: int | None = None) -> dict:
    """세션마다 늘린 항목 수. **사슬 끝 상태가 아니라 세션 단위 분포다.**

    사슬 끝 상태에는 세션의 능력과 사슬 안에서의 위치가 섞여 있다 — 뒤쪽 세션은
    앞 세션이 완료해 둔 상태를 물려받는다. 위치별로 구분하여 기록해야 그 둘이
    분리된다.

    **중단된 세션은 제외하고 계산한다.** 우리가 도중에 중단시킨 세션이 무엇을 할
    수 있었는지는 관측되지 않았으므로, 그 0을 능력의 분포에 포함하면 우리가 만든
    값을 관측으로 보고하는 것이 된다.

    이것은 예측이 아니라 서술 통계다. `harness/anchor.md` 의 질문 ① 앞 절반
    (세션마다 능력이 다른가)이 이 과제에서도 성립하는지를 부수적으로 기록한다.
    """
    by_position: dict[int, list[int]] = {}
    every: list[int] = []
    for rows in chains:
        for row in session_rows(rows, at, start):
            if row["gain"] is None or row["cut"]:
                continue
            by_position.setdefault(row["session_index"], []).append(row["gain"])
            every.append(row["gain"])

    ends: list[int] = []
    for rows in chains:
        scores = [value for value in (passed(row) for row in rows)
                  if value is not None]
        if scores:
            ends.append(scores[-1])

    return {
        "by_position": {key: sorted(value)
                        for key, value in sorted(by_position.items())},
        "all": sorted(every),
        "median": statistics.median(every) if every else None,
        "sd": statistics.stdev(every) if len(every) > 1 else None,
        "chain_end": sorted(ends),
    }


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


# ------------------------------------------- 봉인한 예측을 코드에 박는다

#: **관측이 이보다 적으면 답했다고 하지 않는다**(`docs/CUT_PREDICTIONS.md` 4절).
#: 관측이 적게 나온 뒤에 "차이가 유의하지 않다"로 쓰면 한 번도 검정력이 없었던
#: 배치를 음성 결과로 보고하는 것이 된다.
MIN_OCCURRENCES = 8

#: 예측 3 — 끊는 쪽에서 시작된 세션 가운데 끊긴 것의 비율.
CUT_RATE_RANGE = (0.10, 0.35)


def cut_rate(chains: list[list[dict]]) -> float | None:
    """끊는 쪽에서 시작된 세션 가운데 끊긴 것의 비율."""
    rows = [row for chain in chains for row in chain]
    if not rows:
        return None
    return sum(1 for row in rows if row.get("cut")) / len(rows)


def sessions_per_chain(chains: list[list[dict]]) -> list[int]:
    return [len(chain) for chain in chains]


def cut_sessions_lost_nothing(chains: list[list[dict]],
                              start: int | None = None) -> bool | None:
    """예측 5 — 끊긴 세션 전후로 달성 항목이 줄지 않았는가.

    열 호출 안에 편집이 일어날 수 있고 반쯤 된 채 끊길 수 있다. 줄었다면
    끊는 시점을 편집 전으로 옮겨야 한다.
    """
    judged = False
    for chain in chains:
        before = start
        for row in chain:
            after = passed(row)
            if row.get("cut") and before is not None and after is not None:
                judged = True
                if after < before:
                    return False
            if after is not None:
                before = after
    return True if judged else None


def check_predictions(result: dict, keep: list[list[dict]],
                      cut: list[list[dict]],
                      start: int | None = None) -> list[dict]:
    """봉인한 예측과 대조한다. **문턱은 이 파일에 박혀 있다.**

    예측 6(인계 문서가 남는가)은 여기서 판정하지 않는다 — 그것은 트랜스크립트를
    읽는 탐지기의 일이고, `pilot/analysis/chain_eval.py` 가 이미 계산한다.
    같은 것을 두 군데서 읽으면 한쪽만 고쳐진다.
    """
    keep_side, cut_side = result["keep"], result["cut"]
    spread = result["replacement_spread"]
    out: list[dict] = []

    def add(number: int, says: str, got) -> None:
        out.append({"prediction": number, "says": says, "held": got})

    if keep_side["judged"] < MIN_OCCURRENCES:
        add(0, f"안 끊는 쪽에 깃발이 {MIN_OCCURRENCES}자리 이상 선다", None)
    else:
        add(0, f"안 끊는 쪽에 깃발이 {MIN_OCCURRENCES}자리 이상 선다", True)

    one = (None if keep_side["gain_per_call_median"] is None
           or cut_side["gain_per_call_median"] is None
           else cut_side["gain_per_call_median"]
           > keep_side["gain_per_call_median"])
    add(1, "끊는 쪽이 호출당 더 많이 얻는다", one)

    keep_n = sessions_per_chain(keep)
    cut_n = sessions_per_chain(cut)
    two = (None if not keep_n or not cut_n
           else statistics.median(cut_n) > statistics.median(keep_n))
    add(2, "끊는 쪽에서 세션이 더 많이 돈다", two)

    rate = cut_rate(cut)
    low, high = CUT_RATE_RANGE
    add(3, f"끊긴 세션의 비율이 {low:.0%}~{high:.0%}",
        None if rate is None else low <= rate <= high)

    four = (None if spread.get("baseline") is None
            else spread["better"] > spread["worse"])
    add(4, "교체된 세션이 나은 경우가 더 많다", four)

    add(5, "끊긴 세션이 저장소를 망가뜨리지 않는다",
        cut_sessions_lost_nothing(cut, start))

    # 예측 7 — 초반 신호가 새 자료에서도 서는가. **안 끊는 쪽에서만 판정한다.**
    # 깃발이 선 세션이 관측 하한에 못 미치면 참도 거짓도 아니고 판정 불가다.
    split = result.get("signal_split") or {}
    flag = split.get("flagged") or {}
    plain = split.get("unflagged") or {}
    seven = None
    if (flag.get("rate") is not None and plain.get("rate") is not None
            and flag.get("n", 0) >= MIN_OCCURRENCES):
        seven = plain["rate"] > flag["rate"]
    add(7, "깃발이 안 선 세션이 항목을 늘린 비율이 더 높다", seven)
    return out


def plateau_index(rows: list[dict]) -> int:
    """그 사슬이 **최종 통과 항목 수에 처음 도달한** 세션의 자리(0부터).

    그 뒤에 실행된 세션들은 늘릴 항목이 남아 있지 않다. 어느 갈래든 그
    자리에서는 성과가 0일 수밖에 없으므로, 두 갈래를 견주는 데 쓸 수 없다.
    """
    values = [passed(row) for row in rows]
    final = values[-1] if values else None
    if final is None:
        return len(rows)
    return next((index for index, value in enumerate(values)
                 if value is not None and value >= final), len(rows))


def live_gain_per_call(chains: list[list[dict]], at: int = DEFAULT_AT,
                       start: int | None = None) -> dict:
    """1차 지표를 **사슬이 아직 안 끝난 자리로만** 한정해 다시 산출한다.

    **사후 분석이다. 봉인된 예측 1의 판정을 이것으로 바꾸지 않는다.** 이
    한정은 결과를 본 뒤에 정한 것이므로 검정이 아니라, 다음 배치를 다르게
    설계해야 하는 이유다.

    **왜 필요한가**(2026-08-23에 관측). 안 끊는 쪽 사슬 열 개가 모두 세션
    3~7번째에 최종 항목 수에 도달하고, 그 뒤로 8~24세션을 더 실행했다. 그
    결과 깃발이 선 자리 39개 중 29개(74%)가 **이미 끝난 사슬**에 있었다.
    봉인된 1차 지표는 그 자리들을 그대로 담았다.
    """
    rates: list[float] = []
    for rows in chains:
        cap = plateau_index(rows)
        for mark in _with_replacements(rows, at, start):
            if (mark["session_index"] - 1) > cap:
                continue
            got = mark.get("replacement")
            if mark["cut"]:
                if not got:
                    continue
                gain, spent = got["gain"], mark["calls"] + got["calls"]
            else:
                gain, spent = mark["gain"], mark["calls"]
            rate = per_call(gain, spent)
            if rate is not None:
                rates.append(rate)
    return {
        "judged": len(rates),
        "gain_per_call": sorted(rates),
        "gain_per_call_median": statistics.median(rates) if rates else None,
    }


def finished_early(chains: list[list[dict]]) -> dict:
    """사슬이 언제 끝났고, 그 뒤로 세션과 호출을 얼마나 더 썼는가."""
    reached, after, calls_after, calls_all, flagged_after, flagged_all = (
        [], 0, 0, 0, 0, 0)
    for rows in chains:
        cap = plateau_index(rows)
        reached.append(cap + 1)
        for index, row in enumerate(rows):
            calls_all += calls_of(row)
            is_after = index > cap
            if is_after:
                after += 1
                calls_after += calls_of(row)
            if flagged(row):
                flagged_all += 1
                if is_after:
                    flagged_after += 1
    return {
        "reached_at": sorted(reached),
        "reached_at_median": statistics.median(reached) if reached else None,
        "sessions_after": after,
        "calls_after": calls_after,
        "calls_total": calls_all,
        "flagged_after": flagged_after,
        "flagged_total": flagged_all,
    }


def report(keep_dir: Path, cut_dir: Path, at: int = DEFAULT_AT,
           start: int | None = None) -> dict:
    keep = load_arm(keep_dir)
    cut = load_arm(cut_dir)
    keep_side = arm_summary(keep, at, start)
    cut_side = arm_summary(cut, at, start)
    result = {
        "at": at,
        "start_state": start,
        "keep": keep_side,
        "cut": cut_side,
        "replacement_spread": replacement_spread(
            cut, keep_side["gains"], at, start),
        "sessions_per_chain": {"keep": sessions_per_chain(keep),
                               "cut": sessions_per_chain(cut)},
        "cut_rate": cut_rate(cut),
        # 아래 둘은 **안 끊는 쪽에서만** 낸다. 끊는 쪽은 깃발이 선 세션을
        # 우리가 도중에 끝내므로 그 세션의 성과가 관측되지 않는다.
        "signal_split": signal_split(keep, at, start),
        "gain_spread": gain_spread(keep, at, start),
        # 아래 둘은 **봉인되지 않은 사후 분석**이다. 예측 판정에 쓰지 않는다.
        "finished_early": {"keep": finished_early(keep),
                           "cut": finished_early(cut)},
        "live_gain_per_call": {"keep": live_gain_per_call(keep, at, start),
                               "cut": live_gain_per_call(cut, at, start)},
    }
    result["predictions"] = check_predictions(result, keep, cut, start)
    return result


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

    split = result.get("signal_split")
    if split:
        lines += ["", "## 초반 신호가 새 자료에서도 재현되는가 (안 끊는 쪽)", ""]
        lines.append("깃발이 섰다는 것은 초반 10호출에 `.py` 파일을 한 번도 "
                     "열지 않았다는 뜻이다. 앞 배치에서는 깃발이 선 세션의 "
                     "33%, 안 선 세션의 74%가 달성 항목을 늘렸다. **그 수치는 "
                     "무엇을 관측할지를 그 배치 전부를 보고 선택한 값이므로 "
                     "낙관적이다.**")
        lines.append("")
        lines.append("| 초반 10호출에 `.py` 를 | 세션 | 항목을 늘림 |")
        lines.append("|---|---|---|")
        for name, key in (("하나도 안 열었다(깃발)", "flagged"),
                          ("하나 이상 열었다", "unflagged")):
            side = split.get(key) or {}
            rate = side.get("rate")
            lines.append(
                f"| {name} | {side.get('n', 0)} | {side.get('raised', 0)}"
                f"{'' if rate is None else f' ({rate:.0%})'} |")

    spread_by_session = result.get("gain_spread")
    if spread_by_session:
        lines += ["", "## 세션마다 얼마를 늘렸는가 (안 끊는 쪽)", ""]
        lines.append("**예측이 아니라 서술 통계다** — 자료의 분포를 요약해 "
                     "기술할 뿐 가설을 검정하지 않는다. **사슬 끝 상태가 "
                     "아니라 세션 단위 분포다.** 사슬 끝 상태에는 세션의 "
                     "능력과 사슬 안에서의 위치가 섞여 있다. 중단된 세션은 "
                     "제외했다.")
        lines.append("")
        lines.append(f"- 세션마다 늘린 항목 수(정렬): "
                     f"{spread_by_session['all']}")
        median = spread_by_session.get("median")
        deviation = spread_by_session.get("sd")
        lines.append(
            f"- 중앙값 {'—' if median is None else median} / 표준편차 "
            f"{'—' if deviation is None else f'{deviation:.2f}'}")
        lines.append(f"- 사슬 끝 상태(정렬): {spread_by_session['chain_end']}")
        lines.append("")
        lines.append("| 사슬 안 몇 번째 세션인가 | 늘린 항목 수 |")
        lines.append("|---|---|")
        for position, gains in spread_by_session["by_position"].items():
            lines.append(f"| {position} | {gains} |")

    checks = result.get("predictions") or []
    if checks:
        # **빗나간 것을 먼저 적는다**(`docs/CUT_PREDICTIONS.md` 9절).
        order = {False: 0, None: 1, True: 2}
        lines += ["", "## 봉인한 예측과의 대조", "",
                  "**빗나간 것을 먼저 적는다.**", "",
                  "| | 예측 | 결과 |", "|---|---|---|"]
        for item in sorted(checks, key=lambda c: order[c["held"]]):
            got = {False: "**빗나감**", None: "판정 불가",
                   True: "맞음"}[item["held"]]
            label = "관측 하한" if item["prediction"] == 0 else item["prediction"]
            lines.append(f"| {label} | {item['says']} | {got} |")
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
