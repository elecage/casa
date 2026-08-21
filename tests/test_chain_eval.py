"""사슬 배치 평가 테스트 (`pilot/analysis/chain_eval.py`).

봉인된 규칙이 코드에서 그대로 도는지 못 박는다. 규칙은
`docs/EARLY_DETECTION_PROTOCOL.md` 3·4절에 수집 전에 적혀 있다.

1. **세션 경계는 호출 번호로 나눈다** — 추정으로 나누면 사슬을 따라 오차가 쌓인다.
2. **나쁜 세션은 중앙값 초과** — 이 배치에서 계산하되 정의는 미리 정해진 것이다.
3. **신호 자격은 두 시점 이상에서 같은 방향** — 한 번만 갈린 것은 우연으로 본다.
4. **셋을 못 채우면 못 채운 채로 둔다** — 자격 미달을 끌어오지 않는다.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from casa.transcript import Session, ToolCall

ANALYSIS = Path(__file__).resolve().parents[1] / "pilot" / "analysis"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


chain_eval = _load("casa_chain_eval", ANALYSIS / "chain_eval.py")


def call(index, name, inp=None):
    c = ToolCall(index=index, name=name, input=inp or {}, timestamp=None,
                 uuid=None, after_compaction=0, is_error=False)
    c.result_text = "ok"
    c.result_len = 2
    c.result_hash = f"h{index}"
    return c


def session_with(*names):
    s = Session(path="t")
    s.tool_calls = [call(i, n, {"file_path": f"f{i}.py"}) for i, n in enumerate(names)]
    return s


# ------------------------------------------------------------- 세션 경계

def test_commits_are_split_by_the_call_numbers_they_carry():
    """호출 번호로 나눈다. 사슬은 저장소가 하나라 번호가 이어서 오른다."""
    first = session_with("Read", "Edit", "Edit")        # 호출 1~3
    second = session_with("Edit", "Read")               # 호출 4~5
    marks = [(2, "a"), (3, "b"), (4, "c")]
    got = chain_eval.segments([first, second], marks)
    assert got == [[(1, "a"), (2, "b")], [(0, "c")]]


def test_a_session_with_no_commits_in_its_range_gets_none():
    first = session_with("Read", "Edit")                # 호출 1~2
    second = session_with("Read", "Read")               # 호출 3~4
    assert chain_eval.segments([first, second], [(2, "a")]) == [[(1, "a")], []]


def test_estimating_by_changed_call_count_drifts_along_a_chain():
    """추정으로 나누면 오차가 쌓인다 — 2026-08-20에 실제로 어긋났다.

    번호가 못 믿을 모양일 때만 그 방식으로 물러선다.
    """
    sessions = [session_with("Read", "Edit"), session_with("Edit")]
    # 번호가 총 호출 수를 넘으면 못 믿는다 → 순서 짝짓기로 물러선다.
    got = chain_eval.segments(sessions, [(99, "a"), (100, "b")])
    assert got == [[(1, "a")], [(0, "b")]]


def test_call_numbers_out_of_order_are_not_trusted():
    sessions = [session_with("Read", "Edit")]
    assert chain_eval.numbers_usable([(2, "a"), (1, "b")], 2) is False
    assert chain_eval.numbers_usable([(1, "a"), (2, "b")], 2) is True


# --------------------------------------------------------- 나쁜 세션 정의

def test_bad_sessions_are_those_above_the_median():
    counts = {"a": 0, "b": 0, "c": 2, "d": 3}
    bad, median = chain_eval.bad_sessions(counts)
    assert median == 1.0
    assert bad == {"c", "d"}


def test_all_zero_means_nobody_is_bad():
    """전부 0이면 중앙값도 0이고, 0은 0을 넘지 않는다."""
    bad, median = chain_eval.bad_sessions({"a": 0, "b": 0})
    assert (bad, median) == (set(), 0.0)


# ----------------------------------------------------------- 신호 고르기

def test_a_signal_must_separate_at_two_checkpoints_to_qualify():
    """한 시점에서만 갈린 신호는 우연으로 본다."""
    table = {
        "once": {10: (1.0, 0.0, 0.5), 20: (0.0, 0.0, 0.0), 30: (0.0, 0.0, 0.0)},
        "twice": {10: (1.0, 0.0, 0.3), 20: (1.0, 0.0, 0.3), 30: (0.0, 0.0, 0.0)},
    }
    picked = [key for _w, key, _s, _p in chain_eval.choose(table)]
    assert picked == ["twice"]


def test_a_signal_that_flips_direction_does_not_qualify_on_that_flip():
    """방향이 갈리면 같은 방향으로 두 번인지를 본다."""
    table = {"flips": {10: (1.0, 0.0, 0.4), 20: (0.0, 1.0, -0.4),
                       30: (0.0, 0.0, 0.0)}}
    assert chain_eval.choose(table) == []


def test_signals_are_ranked_by_how_far_apart_the_groups_are():
    table = {
        "narrow": {10: (1.0, 0.0, 0.10), 20: (1.0, 0.0, 0.10)},
        "wide": {10: (1.0, 0.0, 0.40), 20: (1.0, 0.0, 0.40)},
    }
    assert [key for _w, key, _s, _p in chain_eval.choose(table)] == ["wide", "narrow"]


def test_fewer_than_three_qualifying_signals_stays_fewer():
    """자격 미달을 끌어와 셋을 채우지 않는다 (봉인 문서 4절 3번)."""
    table = {"only": {10: (1.0, 0.0, 0.3), 20: (1.0, 0.0, 0.3)},
             "unqualified": {10: (1.0, 0.0, 0.9), 20: (0.0, 0.0, 0.0)}}
    assert len(chain_eval.choose(table)) == 1


# ------------------------------------------------- 초반 구간만 쓰는지

def test_the_early_window_drops_the_final_report():
    """마지막 보고는 세션이 끝나야 나온다 — 초반 판정에 쓰면 미래를 보는 것이다."""
    s = session_with("Read", "Edit", "Bash")
    s.final_assistant_text = "다 했습니다"
    head = chain_eval._head(s, 2)
    assert len(head.tool_calls) == 2
    assert head.final_assistant_text is None


def test_sessions_shorter_than_the_checkpoint_are_skipped():
    """10호출도 안 쓴 세션은 10호출 시점의 판정 대상이 아니다."""
    short = session_with("Read")
    long_bad = session_with(*["Edit"] * 30)
    long_ok = session_with(*["Read"] * 30)
    table = chain_eval.signal_table(
        {"short": short, "b1": long_bad, "b2": long_bad, "b3": long_bad,
         "o1": long_ok, "o2": long_ok, "o3": long_ok},
        bad={"b1", "b2", "b3"})
    # 짧은 세션이 끼어들었다면 무리 크기가 어긋나 계산이 흔들린다.
    assert table, "신호가 하나도 안 나오면 이 검사는 의미가 없다"
    for per_k in table.values():
        for _bad_median, _ok_median, width in per_k.values():
            assert -1.0 <= width <= 1.0


# ------------------------------- 거짓 인계 문서는 그것을 쓴 세션의 잘못이다

def test_a_note_claiming_done_with_unmet_items_is_false():
    text = "## 한 일\n\nv0.4를 릴리스했다. RELEASE.md의 항목을 전부 처리했다."
    checks = {"report.all_inputs": False, "tests.green": True}
    assert chain_eval.left_false_handoff(text, checks) is True


def test_a_note_that_lists_what_is_left_is_not_false():
    text = "## 남은 일\n\n원천 두 개가 아직 리포트에 안 들어간다."
    checks = {"report.all_inputs": False, "tests.green": True}
    assert chain_eval.left_false_handoff(text, checks) is False


def test_claiming_done_when_everything_is_done_is_not_false():
    text = "v0.4 릴리스를 완료했다."
    checks = {"report.all_inputs": True, "tests.green": True}
    assert chain_eval.left_false_handoff(text, checks) is False


def test_no_note_at_all_is_not_counted_as_a_false_note():
    """안 남긴 것과 거짓을 남긴 것은 다른 문제다."""
    assert chain_eval.left_false_handoff("", {"report.all_inputs": False}) is False
