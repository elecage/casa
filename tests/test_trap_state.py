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
