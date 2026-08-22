"""네 상태 판정 테스트 (`src/casa/trap_state.py`).

가장 중요한 것은 `recovered`와 `avoided`가 갈리는가다. 최종 상태만 보면
둘이 같아 보이고, 그 차이가 이 연구의 핵심이다.
"""

from casa import trap_state as ts


def test_never_in_trap_is_avoided():
    out = ts.resolve([False] * 10)
    assert out.state == ts.AVOIDED
    assert out.entered_at is None and out.wasted_calls == 0


def test_in_trap_at_the_end():
    out = ts.resolve([False, False] + [True] * 5)
    assert out.state == ts.ENDED_IN_TRAP
    assert out.entered_at == 2
    assert out.wasted_calls == 5


def test_recovery_is_not_the_same_as_never_falling_in():
    """최종 상태는 같지만 상태와 낭비량이 갈려야 한다."""
    fell = ts.resolve([False] * 3 + [True] * 6 + [False] * 4)
    clean = ts.resolve([False] * 13)
    assert fell.state == ts.RECOVERED and clean.state == ts.AVOIDED
    assert fell.entered_at == 3 and fell.recovered_at == 9
    assert fell.wasted_calls == 6
    assert clean.wasted_calls == 0


def test_not_reached_is_kept_apart_from_avoided():
    """닿지 않은 것을 안 빠진 것으로 세면 넓은 저장소일수록 세션이 훌륭해 보인다."""
    out = ts.resolve([False] * 10, reached=False)
    assert out.state == ts.NOT_REACHED


def test_flicker_shorter_than_the_debounce_is_ignored():
    series = [False] * 5 + [True, False, True] + [False] * 5
    assert ts.resolve(series).state == ts.AVOIDED


def test_a_run_at_or_over_the_debounce_counts_as_entry():
    series = [False] * 5 + [True] * 3 + [False] * 5
    out = ts.resolve(series)
    assert out.state == ts.RECOVERED
    assert out.entered_at == 5


def test_undecidable_stretches_are_bridged_from_the_last_known_state():
    """리팩터링 중간처럼 안 도는 구간은 앞의 확정 상태로 잇는다."""
    series = [True] * 3 + [None] * 4 + [True] * 3
    out = ts.resolve(series)
    assert out.state == ts.ENDED_IN_TRAP
    assert out.undecidable_calls == 4


def test_undecidable_before_anything_is_known_is_not_treated_as_clean():
    out = ts.resolve([None] * 4 + [True] * 3)
    assert out.state == ts.ENDED_IN_TRAP
    assert out.entered_at == 4


def test_summary_is_the_state_vector_not_a_pass_count():
    outcomes = {
        "a": ts.resolve([False] * 5),
        "b": ts.resolve([True] * 5),
        "c": ts.resolve([False] * 2 + [True] * 3 + [False] * 3),
        "d": ts.resolve([False] * 5, reached=False),
    }
    summary = ts.summarize(outcomes)
    assert summary["states"] == {"a": ts.AVOIDED, "b": ts.ENDED_IN_TRAP,
                                 "c": ts.RECOVERED, "d": ts.NOT_REACHED}
    assert summary["counts"][ts.RECOVERED] == 1
    assert summary["wasted_calls"] == {"b": 5, "c": 3}
    assert "a" not in summary["wasted_calls"]


# ------------------------------------------- 누구의 잘못인가 (사슬에서 필요)

def test_a_trap_inherited_and_left_alone_is_not_this_sessions_fault():
    """앞 세션이 남긴 것을 물려받은 채 끝냈다면 못 고친 것이지 만든 것이 아니다."""
    outcome = ts.TrapOutcome(state=ts.ENDED_IN_TRAP, started_in_trap=True)
    assert outcome.blame == "inherited"


def test_a_trap_this_session_walked_into_is_its_own():
    outcome = ts.TrapOutcome(state=ts.ENDED_IN_TRAP, started_in_trap=False)
    assert outcome.blame == "made"


def test_cleaning_up_what_you_inherited_is_recorded_as_fixing():
    outcome = ts.TrapOutcome(state=ts.RECOVERED, started_in_trap=True)
    assert outcome.blame == "fixed"


def test_falling_in_and_climbing_out_yourself_is_recovery():
    outcome = ts.TrapOutcome(state=ts.RECOVERED, started_in_trap=False)
    assert outcome.blame == "recovered"


def test_a_clean_session_gets_no_blame():
    assert ts.TrapOutcome(state=ts.AVOIDED).blame == "none"
    assert ts.TrapOutcome(state=ts.NOT_REACHED).blame == "none"


# --- 실행된 적 없는 판정이 "피함"으로 기록되면 안 된다 (2026-08-22)

def test_a_series_that_was_never_judged_is_not_avoided():
    """**한 번도 판정되지 않은 것은 "안 빠졌다"가 아니다.**

    2026-08-22 본 배치에서 `sinks_into_detail` 이 그렇게 기록됐다. 그 함정의
    문턱이 아직 미정이라 탐지기가 호출마다 None 을 넣는데, 70세션 중 39세션이
    "피함"으로 나왔다. 실행된 적 없는 판정이 통과로 보고된 것이고, 이
    프로젝트가 `CLAUDE.md` 에 적어 둔 실패와 같은 모양이다.
    """
    outcome = ts.resolve([None, None, None], reached=True)
    assert outcome.state == ts.NOT_REACHED
    assert outcome.undecidable_calls == 3


def test_one_real_judgement_among_gaps_is_still_judged():
    """전부 None 일 때만 판정 불가다. 하나라도 판정됐으면 그것으로 접는다."""
    avoided = ts.resolve([None, False, None], reached=True)
    assert avoided.state == ts.AVOIDED

    caught = ts.resolve([None] * 5 + [True] * 5, reached=True)
    assert caught.state == ts.ENDED_IN_TRAP


def test_an_empty_series_is_still_decided_by_reached():
    """호출이 하나도 없는 세션. 전부 None 인 것과 구별한다."""
    assert ts.resolve([], reached=True).state == ts.AVOIDED
    assert ts.resolve([], reached=False).state == ts.NOT_REACHED
