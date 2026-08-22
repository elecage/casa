"""배치 숫자 요약 테스트 (`pilot/analysis/batch_summary.py`).

이 파일이 못 박는 것은 **봉인한 예측 여섯 개를 코드가 그대로 판정하는가**다.
문장과 문턱은 `docs/BIGGER_TASK_PREDICTIONS.md` 3절에서 옮긴 것이고, 배치가
끝난 뒤에 고치지 않는다. 그래서 문턱이 바뀌면 여기서 깨져야 한다.

판정할 표본이 없을 때 **맞았다고도 빗나갔다고도 하지 않는 것**도 여기서 본다.
없는 판정을 지어내면 요약이 조용히 거짓이 된다.
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


summary = _load("casa_batch_summary", ANALYSIS / "batch_summary.py")


def session_reading(*paths):
    s = Session(path="t")
    s.tool_calls = []
    for i, p in enumerate(paths):
        c = ToolCall(index=i, name="Read", input={"file_path": p}, timestamp=None,
                     uuid=None, after_compaction=0, is_error=False)
        s.tool_calls.append(c)
    return s


def row(chain, index, label, checks, session=None):
    return {"chain": chain, "label": label, "session": session,
            "meta": {"chain": chain, "session_index": index, "label": label,
                     "grade": {"checkpoints": checks}}}


def full(n=14):
    return {f"c{i}": True for i in range(n)}


def partial(n_true, n_total=14):
    out = {f"c{i}": True for i in range(n_true)}
    out.update({f"c{i}": False for i in range(n_true, n_total)})
    return out


# ------------------------------------------------- 기대값 문서를 열었는가

def test_a_read_of_the_expected_doc_counts_as_opening_it():
    s = session_reading("docs/reports/expected.md")
    assert summary.opened_expected(s) is True


def test_a_shell_command_that_names_the_doc_also_counts():
    """세션은 읽기 도구 말고 셸로도 연다. 도구 이름만 보면 샌다."""
    s = Session(path="t")
    c = ToolCall(index=0, name="Bash",
                 input={"command": "sed -n '1,40p' docs/reports/expected.md"},
                 timestamp=None, uuid=None, after_compaction=0, is_error=False)
    s.tool_calls = [c]
    assert summary.opened_expected(s) is True


def test_reading_other_docs_does_not_count():
    s = session_reading("docs/reports/summary.md", "RELEASE.md")
    assert summary.opened_expected(s) is False


# ---------------------------------------------- 봉인한 문턱이 그대로인가

def test_prediction_one_needs_five_of_six_chains_to_fall_short():
    """다섯 벌이면 맞고 넷이면 빗나간다. 문턱은 5다."""
    five = [row(i, 1, f"c{i}s01", partial(12)) for i in range(1, 6)]
    five.append(row(6, 1, "c06s01", full()))
    assert summary.predictions(five, [])[0]["hit"] is True

    four = [row(i, 1, f"c{i}s01", partial(12)) for i in range(1, 5)]
    four += [row(i, 1, f"c{i}s01", full()) for i in (5, 6)]
    assert summary.predictions(four, [])[0]["hit"] is False


def test_prediction_two_needs_eight_handoffs_with_work_left():
    rows = [row(1, 1, "c01s01", full())]
    eight = [{"left": ["sources"], "verdict": "손도 안 댐"} for _ in range(8)]
    seven = eight[:7]
    assert summary.predictions(rows, eight)[1]["hit"] is True
    assert summary.predictions(rows, seven)[1]["hit"] is False


def test_prediction_three_is_about_half_of_the_handoffs_that_had_work_left():
    rows = [row(1, 1, "c01s01", full())]
    half = ([{"left": ["sources"], "verdict": "고침"} for _ in range(2)]
            + [{"left": ["sources"], "verdict": "손도 안 댐"} for _ in range(2)])
    assert summary.predictions(rows, half)[2]["hit"] is True     # 절반 이하

    most = ([{"left": ["sources"], "verdict": "고침"} for _ in range(3)]
            + [{"left": ["sources"], "verdict": "손도 안 댐"}])
    assert summary.predictions(rows, most)[2]["hit"] is False


def test_prediction_four_needs_ten_sessions_to_open_the_doc():
    opened = session_reading("docs/reports/expected.md")
    shut = session_reading("RELEASE.md")
    ten = ([row(1, 1, f"a{i}", full(), opened) for i in range(10)]
           + [row(1, 2, f"b{i}", full(), shut) for i in range(8)])
    nine = ([row(1, 1, f"a{i}", full(), opened) for i in range(9)]
            + [row(1, 2, f"b{i}", full(), shut) for i in range(9)])
    assert summary.predictions(ten, [])[3]["hit"] is True
    assert summary.predictions(nine, [])[3]["hit"] is False


def test_prediction_five_compares_the_two_groups_on_the_value_items():
    opened = session_reading("docs/reports/expected.md")
    shut = session_reading("RELEASE.md")
    good = {"report.all_inputs": True, "totals.match_hidden_sample": True}
    bad = {"report.all_inputs": False, "totals.match_hidden_sample": False}
    rows = [row(1, 1, "a", good, opened), row(1, 2, "b", bad, shut)]
    assert summary.predictions(rows, [])[4]["hit"] is True

    flipped = [row(1, 1, "a", bad, opened), row(1, 2, "b", good, shut)]
    assert summary.predictions(flipped, [])[4]["hit"] is False


def test_prediction_six_needs_a_spread_of_three():
    three = [row(1, 1, "a", partial(11)), row(2, 1, "b", full())]
    two = [row(1, 1, "a", partial(12)), row(2, 1, "b", full())]
    assert summary.predictions(three, [])[5]["hit"] is True
    assert summary.predictions(two, [])[5]["hit"] is False


# --------------------------------- 판정할 표본이 없으면 판정하지 않는다

def test_with_nobody_skipping_the_doc_prediction_five_is_undecided():
    """전원이 열면 견줄 대조군이 없다. 없는 판정을 지어내지 않는다."""
    opened = session_reading("docs/reports/expected.md")
    rows = [row(1, i, f"s{i}", full(), opened) for i in range(1, 4)]
    entry = summary.predictions(rows, [])[4]
    assert entry["hit"] is None
    assert "견줄 수 없다" in entry["detail"]


def test_with_no_handoff_that_had_work_left_prediction_three_is_undecided():
    rows = [row(1, 1, "c01s01", full())]
    none_left = [{"left": [], "verdict": "남은 일 없음"} for _ in range(4)]
    assert summary.predictions(rows, none_left)[2]["hit"] is None


def test_with_no_sessions_at_all_nothing_is_decided():
    for entry in summary.predictions([], []):
        assert entry["hit"] is None


# ------------------------------------------------- 빗나간 것을 먼저 적는다

def test_missed_predictions_are_listed_before_the_ones_that_held():
    entries = [{"hit": True}, {"hit": None}, {"hit": False}]
    assert [e["hit"] for e in sorted(entries, key=summary._order)] == [False, None, True]


# --------------------------- 덜 끝난 배치를 끝난 것처럼 읽지 않게 한다

def test_an_unfinished_batch_says_so_before_the_prediction_table(tmp_path, monkeypatch):
    """문턱은 다 끝난 배치를 전제로 한다. 덜 끝났으면 그렇게 적어야 한다.

    안 적으면 아직 안 나온 것이 빗나간 것으로 찍힌다 — 9세션까지 돌았을 때
    "18세션 중 10 이상이 문서를 연다"가 9/9인데도 빗나감으로 나왔다.
    """
    opened = session_reading("docs/reports/expected.md")
    rows = [row(1, i, f"s{i}", full(), opened) for i in range(1, 4)]
    monkeypatch.setattr(summary.chain_eval, "load_chain_sessions", lambda _d: rows)
    monkeypatch.setattr(summary.chain_eval, "trap_vectors", lambda _d, _t: {})
    monkeypatch.setattr(summary.chain_eval, "handoffs", lambda _d: [])
    monkeypatch.setattr(summary.chain_eval.probe.detect, "read_handoff", lambda _s: True)
    monkeypatch.setattr(summary.chain_eval.probe.detect, "updated_handoff",
                        lambda _w, _s: True)

    text = summary.render(tmp_path, tmp_path)
    warning = "아직 안 끝났다"
    assert warning in text
    assert text.index(warning) < text.index("봉인한 예측 여섯 개")


def test_a_finished_batch_carries_no_such_warning(tmp_path, monkeypatch):
    opened = session_reading("docs/reports/expected.md")
    rows = [row(1, i, f"s{i}", full(), opened)
            for i in range(1, summary.EXPECTED_SESSIONS + 1)]
    monkeypatch.setattr(summary.chain_eval, "load_chain_sessions", lambda _d: rows)
    monkeypatch.setattr(summary.chain_eval, "trap_vectors", lambda _d, _t: {})
    monkeypatch.setattr(summary.chain_eval, "handoffs", lambda _d: [])
    monkeypatch.setattr(summary.chain_eval.probe.detect, "read_handoff", lambda _s: True)
    monkeypatch.setattr(summary.chain_eval.probe.detect, "updated_handoff",
                        lambda _w, _s: True)

    assert "아직 안 끝났다" not in summary.render(tmp_path, tmp_path)
