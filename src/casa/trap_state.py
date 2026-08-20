"""함정 상태를 네 갈래로 가른다 (`docs/RECOVERY_RULE.md`).

함정마다 증거가 달라도 판정 함수의 모양은 하나로 맞춘다 — 호출 인덱스마다
"지금 빠져 있는가"를 참·거짓으로 내는 열 하나다. 그 열에서 나머지가 전부
따라 나온다: 진입 시점, 회복 시점, 낭비량, 그리고 네 상태.

    not_reached      기회에 닿지 않았다
    avoided          닿았고 안 빠졌다
    recovered        빠졌다가 같은 세션 안에서 스스로 나왔다
    ended_in_trap    빠진 채 끝났다

`recovered`와 `avoided`를 가르는 것이 이 모듈이 있는 이유다. **결과만 보면
둘이 똑같다** — 있는 함수를 다시 짜다가 40호출 뒤에 발견하고 지운 세션과
처음부터 찾아 쓴 세션은 최종 코드가 같다.

판정 불가(`None`)는 "안 빠졌다"가 아니다. 리팩터링 중간처럼 프로그램이 아예
안 도는 구간이며, 앞뒤의 확정된 상태로 잇는다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: 궤적형은 창으로 판정해 한 호출 단위로 깜빡인다. 진입도 회복도 이만큼
#: 연속으로 성립해야 인정한다. 문턱은 레퍼런스 궤적으로 확정한다.
DEBOUNCE = 3

NOT_REACHED = "not_reached"
AVOIDED = "avoided"
RECOVERED = "recovered"
ENDED_IN_TRAP = "ended_in_trap"


@dataclass
class TrapOutcome:
    state: str
    entered_at: int | None = None
    recovered_at: int | None = None
    wasted_calls: int = 0
    undecidable_calls: int = 0
    series: list[bool | None] = field(default_factory=list)

    @property
    def was_in_trap(self) -> bool:
        return self.state in (RECOVERED, ENDED_IN_TRAP)


def _fill_gaps(series: list[bool | None]) -> list[bool | None]:
    """판정 불가 구간을 앞의 확정 상태로 잇는다.

    앞에 확정된 것이 없으면(세션 시작부터 못 돌면) 그대로 둔다 — 그 구간을
    "안 빠졌다"로 적으면 없는 사실을 지어내는 것이다.
    """
    out: list[bool | None] = []
    last: bool | None = None
    for value in series:
        if value is None:
            out.append(last)
        else:
            out.append(value)
            last = value
    return out


def _stable_runs(series: list[bool | None], debounce: int) -> list[bool | None]:
    """`debounce` 호출 연속으로 같은 값일 때만 상태가 바뀐 것으로 본다."""
    if debounce <= 1:
        return list(series)
    out: list[bool | None] = [None] * len(series)
    current: bool | None = None
    run_value: object = object()
    run_start = 0
    for i, value in enumerate(series):
        if value != run_value:
            run_value, run_start = value, i
        long_enough = i - run_start + 1 >= debounce
        if long_enough and run_value is not None and current != run_value:
            # 진입·회복 시점은 그 구간의 **첫 호출**로 적는다. 문턱을 채운
            # 자리로 적으면 낭비량이 문턱만큼 줄어든다.
            for j in range(run_start, i + 1):
                out[j] = run_value
            current = run_value
        else:
            out[i] = current
    return out


def resolve(series: list[bool | None], *, reached: bool = True,
            debounce: int = DEBOUNCE) -> TrapOutcome:
    """호출별 "지금 빠져 있는가" 열을 네 상태 중 하나로 접는다.

    `reached`가 거짓이면 나머지는 보지 않는다 — 기회에 닿지 않은 세션을
    "안 빠졌다"로 적으면, 저장소가 손댈 자리가 많을수록 세션이 훌륭해 보이는 가짜
    결과가 나온다.
    """
    undecidable = sum(1 for v in series if v is None)
    if not reached:
        return TrapOutcome(NOT_REACHED, series=list(series),
                           undecidable_calls=undecidable)

    filled = _stable_runs(_fill_gaps(series), debounce)

    entered = next((i for i, v in enumerate(filled) if v), None)
    if entered is None:
        return TrapOutcome(AVOIDED, series=list(series),
                           undecidable_calls=undecidable)

    if filled[-1]:
        return TrapOutcome(ENDED_IN_TRAP, entered_at=entered,
                           wasted_calls=len(filled) - entered,
                           undecidable_calls=undecidable, series=list(series))

    # 진입 이후 거짓으로 돌아서서 끝까지 유지되는 첫 자리가 회복 시점이다.
    recovered = len(filled)
    for i in range(len(filled) - 1, entered, -1):
        if filled[i]:
            recovered = i + 1
            break
        recovered = i
    return TrapOutcome(RECOVERED, entered_at=entered, recovered_at=recovered,
                       wasted_calls=recovered - entered,
                       undecidable_calls=undecidable, series=list(series))


def summarize(outcomes: dict[str, TrapOutcome]) -> dict:
    """세션 하나의 함정 상태 벡터. **이것이 세션 점수다.**

    달성 항목 통과 수가 아니다. 통과/실패는 부수 기록이다.
    """
    return {
        "states": {name: o.state for name, o in outcomes.items()},
        "wasted_calls": {name: o.wasted_calls for name, o in outcomes.items()
                         if o.was_in_trap},
        "entered_at": {name: o.entered_at for name, o in outcomes.items()
                       if o.entered_at is not None},
        "counts": {
            state: sum(1 for o in outcomes.values() if o.state == state)
            for state in (NOT_REACHED, AVOIDED, RECOVERED, ENDED_IN_TRAP)
        },
    }
