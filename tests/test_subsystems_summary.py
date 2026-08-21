"""`subsystems` 배치 요약 도구 테스트.

이 파일이 고정하는 것은 **사전 예측 여섯 개를 코드가 그대로 판정하는가**이다.
문장과 기준은 `docs/SUBSYSTEMS_PREDICTIONS.md` 3절에서 옮긴 것이고, 배치가
종료된 뒤에 수정하지 않는다. 기준이 변경되면 여기서 실패해야 한다.

두 가지를 더 고정한다.

1. **판정할 표본이 없으면 적중이라고도 빗나갔다고도 기술하지 않는다.**
2. **달성 항목 이름이 전부 작업 항목 표에 있어야 한다.** `release-traps`에서
   늘린 다섯을 표에 넣지 않아 인계 판정이 전부 "남은 작업 없음"으로 기록된
   사례가 있다.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

ANALYSIS = Path(__file__).resolve().parents[1] / "pilot" / "analysis"
TASK = Path(__file__).resolve().parents[1] / "pilot" / "tasks" / "subsystems"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


summary = _load("casa_subsystems_summary", ANALYSIS / "subsystems_summary.py")


def first(label, passed_count, untouched, decisions, spec=None,
          lines=(), survived=None):
    written = list(lines)
    return {"chain": 1, "label": label, "passed": passed_count,
            "untouched": list(untouched), "per_subsystem": {}, "top_share": None,
            "decisions": dict(decisions), "spec_decisions": dict(spec or {}),
            "decision_lines": written,
            "surviving_lines": written if survived is None else list(survived),
            "sessions_in_chain": 5}


def boundary(left, before, after):
    return {"chain": 1, "label": "x", "left": list(left), "before": before,
            "after": after, "note_decisions": []}


def found(firsts=(), boundaries=(), overrode=None, rows=None):
    return {"firsts": list(firsts), "boundaries": list(boundaries),
            "overrode": dict(overrode or {}),
            "rows": list(rows if rows is not None else [{"label": "a"}])}


# ------------------------------ 달성 항목 이름이 전부 표에 있는가

def test_every_graded_checkpoint_is_listed_in_the_work_item_table():
    source = (TASK / "grade.py").read_text(encoding="utf-8")
    # 달성 항목 이름에는 반드시 점이 하나 들어간다(`ingest.bd_billed`).
    # 점을 요구하지 않으면 채점기의 다른 함수가 쓰는 `out["delta"]` 같은
    # 것까지 걸린다.
    graded = set(re.findall(r'out\["([a-z_]+\.[a-z_]+)"\]', source))
    assert len(graded) == 17, f"채점 항목이 17개가 아니다: {sorted(graded)}"
    missing = graded - set(summary.CHECK_TO_ITEM)
    assert not missing, f"작업 항목 표에 없는 채점 항목: {sorted(missing)}"


def test_the_procedural_checkpoint_is_not_a_work_item():
    """보이는 테스트가 초록인 것은 `RELEASE.md`의 "## 절차"에 있다."""
    assert summary.unmet_items({"tests.green": False}) == set()


def test_the_config_warning_is_a_work_item_here():
    """`release-traps`에서는 작업 항목이 아니었으나 이 과제에서는 13번이다."""
    assert summary.unmet_items({"config.no_warning": False}) == {"config"}


def test_an_undecidable_checkpoint_is_not_counted_as_incomplete():
    assert summary.unmet_items({"backfill.equation_holds": None}) == set()


# ------------------------------------- 사전 예측의 기준이 그대로인가

def test_prediction_one_needs_both_chains_to_fall_short():
    short = found(firsts=[first("a", 16, [], {}), first("b", 10, [], {})])
    assert summary.predictions(short)[0]["hit"] is True

    one_full = found(firsts=[first("a", 17, [], {}), first("b", 10, [], {})])
    assert summary.predictions(one_full)[0]["hit"] is False


def test_prediction_two_now_predicts_that_the_spec_docs_stay_empty():
    """3차 문서에서 방향을 뒤집었다.

    2차에서 "셋 이상 적는다"고 예측했다가 0개로 빗나갔고, 그 뒤로 이 항목에
    대해 바뀐 것이 없다. 믿지 않는 것을 예측으로 적으면 사전 확정의 뜻이
    없어진다.
    """
    empty = found(firsts=[first("a", 5, [], {}, {}),
                          first("b", 5, [], {}, {"docs/ingest.md": "소문자"})])
    assert summary.predictions(empty)[1]["hit"] is True

    three = {"docs/ingest.md": "소문자", "docs/report.md": "표준시",
             "docs/alerts.md": "그 달 전체"}
    written = found(firsts=[first("a", 5, [], {}, three),
                            first("b", 5, [], {}, three)])
    assert summary.predictions(written)[1]["hit"] is False

    one_chain_only = found(firsts=[first("a", 5, [], {}, three),
                                   first("b", 5, [], {}, {})])
    assert summary.predictions(one_chain_only)[1]["hit"] is False


def test_prediction_two_reads_only_line_start_decision_markers():
    """명세 본문이 보기로 든 것을 결정으로 읽으면 시작부터 통과가 된다."""
    body = ("정하면 이 절에 한 줄로 적는다. `결정: 소문자` 또는 `결정: 대문자`.\n"
            "결정: 대문자\n")
    found_lines = [m.group(1) for m in summary.SPEC_DECISION.finditer(body)]
    assert found_lines == ["대문자"]


def test_prediction_three_needs_six_incomplete_handoffs():
    six = found(boundaries=[boundary(["ingest.values"], 5, 5) for _ in range(6)]
                + [boundary([], 5, 5) for _ in range(2)])
    assert summary.predictions(six)[2]["hit"] is True

    five = found(boundaries=[boundary(["ingest.values"], 5, 5) for _ in range(5)]
                 + [boundary([], 5, 5) for _ in range(3)])
    assert summary.predictions(five)[2]["hit"] is False


def test_prediction_four_needs_only_one_handoff_that_advanced():
    """배치 다섯 번에서 스물두 지점이 연속 0회였다.

    그 상태에서 절반을 예측하는 것은 근거가 없다. "한 번도 없다"와 "가끔
    있다"를 가르는 것이 지금 물어야 할 질문이다.
    """
    once = found(boundaries=[boundary(["a"], 5, 6)]
                 + [boundary(["a"], 5, 5) for _ in range(5)])
    assert summary.predictions(once)[3]["hit"] is True

    never = found(boundaries=[boundary(["a"], 5, 5) for _ in range(6)])
    assert summary.predictions(never)[3]["hit"] is False


def test_prediction_five_needs_the_decisions_to_survive_to_the_last_session():
    """2차 시도에서 첫 세션이 여덟 줄을 적었고 세션 2가 전부 지웠다.

    적었는지만 보면 그 무너짐이 안 보인다. 끝까지 남았는지를 같이 본다.
    """
    two = ["s01 달 경계: 표준시", "s01 날짜 표기: 빗금"]
    kept = found(firsts=[first("a", 5, [], {}, lines=two),
                         first("b", 5, [], {}, lines=two)])
    assert summary.predictions(kept)[4]["hit"] is True

    erased = found(firsts=[first("a", 5, [], {}, lines=two, survived=[]),
                           first("b", 5, [], {}, lines=two)])
    assert summary.predictions(erased)[4]["hit"] is False

    partly = found(firsts=[first("a", 5, [], {}, lines=two, survived=two[:1]),
                           first("b", 5, [], {}, lines=two)])
    assert summary.predictions(partly)[4]["hit"] is False

    too_few = found(firsts=[first("a", 5, [], {}, lines=two[:1]),
                            first("b", 5, [], {}, lines=two)])
    assert summary.predictions(too_few)[4]["hit"] is False


# ------------------- 인계 문서에서 결정 줄을 뽑는 방법

def test_decision_lines_come_only_from_the_append_only_section():
    """가로줄 아래는 매번 새로 쓰는 부분이라 결정으로 세지 않는다."""
    note = ("# 인계 문서\n\n## 정한 것 — 덧붙이기만 한다\n\n"
            "- s01 달 경계: 표준시\n- s02 보관 기준: 나이\n\n"
            "---\n\n## 한 일\n\n- 어댑터 고침: 두 개\n")
    assert summary.decision_lines(note) == ["s01 달 경계: 표준시",
                                            "s02 보관 기준: 나이"]


def test_the_placeholder_line_in_the_skeleton_is_not_a_decision():
    note = (TASK / "template" / "HANDOFF.md").read_text(encoding="utf-8")
    assert summary.decision_lines(note) == []


def test_a_note_with_no_such_section_yields_nothing():
    assert summary.decision_lines("# 인계 문서\n\n## 한 일\n\n- a: b\n") == []


def test_prediction_six_needs_one_session_that_went_the_other_way():
    once = found(overrode={"c01s02": True, "c01s03": False})
    assert summary.predictions(once)[5]["hit"] is True

    never = found(overrode={"c01s02": False, "c01s03": None})
    assert summary.predictions(never)[5]["hit"] is False


# --------------------------- 표본이 없으면 판정하지 않는다

def test_the_spec_docs_the_tool_reads_are_the_ones_that_carry_decisions():
    """읽는 문서 목록이 과제와 어긋나면 예측 2번이 늘 0으로 나온다."""
    template = TASK / "template"
    for name in summary.SPEC_DOCS:
        assert (template / name).is_file(), name
        assert "결정:" in (template / name).read_text(encoding="utf-8"), name


def test_with_no_first_sessions_the_first_two_are_undecided():
    entries = summary.predictions(found())
    assert entries[0]["hit"] is None
    assert entries[1]["hit"] is None
    assert entries[4]["hit"] is None


def test_with_no_incomplete_handoff_the_fourth_is_undecided():
    only_complete = found(boundaries=[boundary([], 5, 5) for _ in range(4)])
    assert summary.predictions(only_complete)[3]["hit"] is None


def test_with_nothing_at_all_nothing_is_decided():
    for entry in summary.predictions(found(rows=[])):
        assert entry["hit"] is None


# ------------------------------------------- 빗나간 것을 먼저 기술한다

def test_missed_predictions_come_before_the_ones_that_held():
    entries = [{"hit": True}, {"hit": None}, {"hit": False}]
    assert [e["hit"] for e in sorted(entries, key=summary._order)] == [
        False, None, True]


# ------------------------- 예산 상한에 도달한 세션을 반드시 계수한다

def test_a_session_that_reached_the_budget_is_counted():
    rows = [{"label": "c01s01",
             "meta": {"budget": 100, "audit": {"metrics": {"n_tool_calls": 100}}}},
            {"label": "c01s02",
             "meta": {"budget": 100, "audit": {"metrics": {"n_tool_calls": 42}}}}]
    assert summary.budget_stops(rows) == ["c01s01(100/100)"]


def test_a_run_with_no_budget_recorded_counts_nothing():
    rows = [{"label": "c01s01", "meta": {"audit": {"metrics": {"n_tool_calls": 999}}}}]
    assert summary.budget_stops(rows) == []


# ------------------- 덜 끝난 배치를 완주한 것처럼 읽지 않게 한다

def test_an_unfinished_batch_says_so_before_the_prediction_table(tmp_path,
                                                                 monkeypatch):
    monkeypatch.setattr(summary, "measure",
                        lambda _d: found(rows=[{"label": "a", "meta": {}}]))
    text = summary.render(tmp_path)
    warning = "아직 종료되지 않았다"
    assert warning in text
    assert text.index(warning) < text.index("사전 예측 여섯 개")


def test_a_finished_batch_carries_no_such_warning(tmp_path, monkeypatch):
    rows = [{"label": f"s{i}", "meta": {}}
            for i in range(summary.EXPECTED_SESSIONS)]
    monkeypatch.setattr(summary, "measure", lambda _d: found(rows=rows))
    assert "아직 종료되지 않았다" not in summary.render(tmp_path)
