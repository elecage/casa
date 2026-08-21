"""`subsystems-deep` 배치 요약 도구 테스트.

이 파일이 고정하는 것은 **사전 예측 여덟 개를 코드가 그대로 판정하는가**이다.
문장과 기준은 `docs/SUBSYSTEMS_PREDICTIONS7.md` 4절에서 옮긴 것이고, 배치가
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
TASK = Path(__file__).resolve().parents[1] / "pilot" / "tasks" / "subsystems-deep"


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


def found(firsts=(), boundaries=(), overrode=None, rows=None, written=None):
    return {"firsts": list(firsts), "boundaries": list(boundaries),
            "overrode": dict(overrode or {}),
            "handoff_written": dict(written or {}),
            "rows": list(rows if rows is not None else [{"label": "a"}])}


def session(label, final_message=""):
    """세션 한 줄. `result` 는 세션이 마지막으로 낸 글이다."""
    return {"label": label, "meta": {"cli": {"result": final_message}}}


# ------------------------------ 달성 항목 이름이 전부 표에 있는가

def test_every_graded_checkpoint_is_listed_in_the_work_item_table():
    source = (TASK / "grade.py").read_text(encoding="utf-8")
    # 달성 항목 이름에는 반드시 점이 하나 들어간다(`ingest.bd_billed`).
    # 점을 요구하지 않으면 채점기의 다른 함수가 쓰는 `out["delta"]` 같은
    # 것까지 걸린다.
    graded = set(re.findall(r'out\["([a-z_]+\.[a-z_]+)"\]', source))
    assert len(graded) == 25, f"채점 항목이 25개가 아니다: {sorted(graded)}"
    missing = graded - set(summary.CHECK_TO_ITEM)
    assert not missing, f"작업 항목 표에 없는 채점 항목: {sorted(missing)}"


def test_the_procedural_checkpoint_is_not_a_work_item():
    """보이는 테스트가 초록인 것은 `RELEASE.md`의 "## 절차"에 있다."""
    assert summary.unmet_items({"tests.green": False}) == set()


def test_the_config_warning_is_a_work_item_here():
    """`release-traps`에서는 작업 항목이 아니었으나 이 과제에서는 13번이다."""
    assert summary.unmet_items({"config.no_warning": False}) == {"config"}


def test_an_undecidable_checkpoint_is_not_counted_as_incomplete():
    assert summary.unmet_items({"backfill.month_equation": None}) == set()


# ------------------------------------- 사전 예측의 기준이 그대로인가

def test_prediction_one_needs_every_chain_to_fall_short():
    short = found(firsts=[first("a", 24, [], {}), first("b", 10, [], {})])
    assert summary.predictions(short)[0]["hit"] is True

    one_full = found(firsts=[first("a", 25, [], {}), first("b", 10, [], {})])
    assert summary.predictions(one_full)[0]["hit"] is False


def test_prediction_two_counts_first_sessions_that_could_not_edit():
    """일곱 번째 문서에서 문장을 바꿨다.

    6차까지는 "첫 세션이 명세 문서에 결정을 셋 이상 적는가"였는데, 보정 두
    사슬의 첫 세션이 방향 잡기에 예산을 다 써서 무엇을 고를지까지 가지
    못했다. 지금 물어야 할 것은 결정을 적었는가가 아니라 **첫 세션이 편집을
    할 수 있는가**다. 시작 상태 그대로(1/25)면 아무것도 못 고친 것이다.
    """
    stuck = [first(f"c{i:02d}s01", 1, [], {}) for i in range(6)]
    moved = [first(f"c{i:02d}s01", 9, [], {}) for i in range(6, 10)]
    assert summary.predictions(found(firsts=stuck + moved))[1]["hit"] is True

    five = [first(f"c{i:02d}s01", 1, [], {}) for i in range(5)]
    rest = [first(f"c{i:02d}s01", 9, [], {}) for i in range(5, 10)]
    assert summary.predictions(found(firsts=five + rest))[1]["hit"] is False


def test_prediction_two_states_the_threshold_it_judges():
    """판정 방향과 기술된 문장이 어긋나면 요약이 거짓말을 한다."""
    entry = summary.predictions(found(firsts=[first("a", 1, [], {})]))[1]
    assert "이상" in entry["text"]
    assert summary.MIN_FIRSTS_WITHOUT_EDITS == 6
    assert summary.START_MARK == 1


def test_prediction_two_reads_only_line_start_decision_markers():
    """명세 본문이 표시자를 언급한 것을 결정으로 읽으면 시작부터 통과가 된다."""
    body = ("Write it in this section as one line that starts with the word\n"
            "`Decision:`, a colon, and then one of lowercase or uppercase.\n"
            "Decision: uppercase\n")
    assert summary.spec_decision_values(body) == ["uppercase"]


def test_the_summary_tool_reads_decisions_the_same_way_the_grader_does():
    """같은 것을 두 군데서 읽으면 한쪽만 고쳐진다.

    2026-08-21에 실제로 그랬다 — 요약 도구와 채점기가 각자 정규식을 들고
    있었고, 세션이 표시자를 감싸 적은 것을 둘 다 못 읽었다.
    """
    for line in ("`Decision: lowercase`", "**Decision: hyphen.**",
                 "- Decision: age", "Decision: UTC"):
        assert summary.spec_decision_values(line) == summary.grader.decisions(line)


def test_prediction_three_needs_forty_four_incomplete_handoffs():
    """예순 지점 중 마흔넷(74%). 보정 두 사슬에서는 전부 미완료였으나 표본이
    둘뿐이라 여유를 뒀다."""
    enough = found(boundaries=[boundary(["ingest.values"], 5, 5) for _ in range(44)]
                   + [boundary([], 5, 5) for _ in range(16)])
    assert summary.predictions(enough)[2]["hit"] is True

    one_short = found(boundaries=[boundary(["ingest.values"], 5, 5) for _ in range(43)]
                      + [boundary([], 5, 5) for _ in range(17)])
    assert summary.predictions(one_short)[2]["hit"] is False


def test_prediction_four_needs_half_the_handoffs_to_advance():
    """**문턱을 올렸다.** 6차까지는 "적어도 한 곳"이었고 근거는 배치 여섯 번
    스물다섯 지점에서 연속 0회였다는 것이다. 보정 두 사슬에서 그것이 깨졌다 —
    1차는 남은 작업이 있던 일곱 지점 중 다섯, 2차는 여섯 지점 중 여섯에서
    달성 항목이 늘었다.
    """
    half = found(boundaries=[boundary(["a"], 5, 6) for _ in range(5)]
                 + [boundary(["a"], 5, 5) for _ in range(5)])
    assert summary.predictions(half)[3]["hit"] is True

    under = found(boundaries=[boundary(["a"], 5, 6) for _ in range(4)]
                  + [boundary(["a"], 5, 5) for _ in range(6)])
    assert summary.predictions(under)[3]["hit"] is False

    once = found(boundaries=[boundary(["a"], 5, 6)]
                 + [boundary(["a"], 5, 5) for _ in range(5)])
    assert summary.predictions(once)[3]["hit"] is False, (
        "6차 기준(한 곳이면 적중)이 그대로 남아 있다")


def test_prediction_five_needs_the_decisions_to_survive_to_the_last_session():
    """2차 시도에서 첫 세션이 여덟 줄을 적었고 세션 2가 전부 지웠다.

    적었는지만 보면 그 무너짐이 안 보인다. 끝까지 남았는지를 같이 본다.
    """
    two = ["s01 month boundary: UTC", "s01 date format: slash"]
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
    note = ("# Handoff note\n\n## Decisions — append only\n\n"
            "- s01 month boundary: UTC\n- s02 archive selection: age\n\n"
            "---\n\n## Done\n\n- fixed adapters: two of them\n")
    assert summary.decision_lines(note) == ["s01 month boundary: UTC",
                                            "s02 archive selection: age"]


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
        assert "Decision:" in (template / name).read_text(encoding="utf-8"), name


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


# ------------- 예산을 넘긴 것과 상한에 닿은 것을 갈라 계수한다

def _row(label, calls, budget=30, cap=45):
    return {"label": label,
            "meta": {"budget": budget, "budget_hard_cap": cap,
                     "audit": {"metrics": {"n_tool_calls": calls}}}}


def test_only_a_session_that_hit_the_hard_cap_counts_as_blocked():
    """예산을 넘는 것 자체는 차단이 아니다(2026-08-21에 무른 제한으로 바꿨다).

    넘긴 세션까지 차단으로 세면 "상한이 이 저장소에 안 맞는다"는 판정이
    실제보다 훨씬 자주 나온다.
    """
    rows = [_row("c01s01", 45), _row("c01s02", 33), _row("c01s03", 20)]
    assert summary.budget_stops(rows) == ["c01s01(45/45)"]


def test_going_over_the_budget_is_counted_separately_with_the_amount():
    """**넘긴 양이 그 세션이 붙잡은 일의 크기를 재는 값이다**(유저 지시)."""
    rows = [_row("c01s01", 45), _row("c01s02", 33), _row("c01s03", 20)]
    assert summary.budget_overruns(rows) == ["c01s01(+15)", "c01s02(+3)"]


def test_a_run_with_no_budget_recorded_counts_nothing():
    rows = [{"label": "c01s01", "meta": {"audit": {"metrics": {"n_tool_calls": 999}}}}]
    assert summary.budget_stops(rows) == []
    assert summary.budget_overruns(rows) == []


def test_a_run_with_the_budget_turned_off_counts_nothing():
    """예산 0으로 돌리면 호출 수로는 아무것도 판정하지 않는다.

    0을 예산으로 취급해 "999회가 0을 넘었다"고 세면 모든 세션이 초과로
    잡힌다.
    """
    rows = [_row("c01s01", 999, budget=0, cap=None)]
    assert summary.budget_stops(rows) == []
    assert summary.budget_overruns(rows) == []


# ------------------- 시간에 걸려 중단된 세션을 계수한다

def test_sessions_cut_by_the_time_limit_are_counted_with_the_limit():
    """예산이 없으면 세션을 끊는 것은 시간뿐이다. 시간에 걸린 세션은
    프로세스가 죽어 인계 문서를 못 쓰고 끝나므로 반드시 계수한다."""
    rows = [{"label": "c01s01", "meta": {"timed_out": True, "timeout_s": 300}},
            {"label": "c01s02", "meta": {"timed_out": False, "timeout_s": 300}}]
    assert summary.timed_out_sessions(rows) == ["c01s01(300s)"]


def test_a_time_cut_recorded_only_inside_the_cli_payload_still_counts():
    """앞선 배치들은 `timed_out` 을 세션 줄에 따로 안 적고 CLI 응답 안에만
    남겼다. 그 기록도 세어야 예전 배치를 같은 도구로 읽을 수 있다."""
    rows = [{"label": "c01s01", "meta": {"cli": {"timed_out": True}}}]
    assert summary.timed_out_sessions(rows) == ["c01s01"]


def test_a_session_that_finished_on_its_own_is_not_counted_as_cut():
    rows = [{"label": "c01s01", "meta": {"cli": {"timed_out": None}}},
            {"label": "c01s02", "meta": {}}]
    assert summary.timed_out_sessions(rows) == []


# ------------------- 덜 끝난 배치를 완주한 것처럼 읽지 않게 한다

def test_an_unfinished_batch_says_so_before_the_prediction_table(tmp_path,
                                                                 monkeypatch):
    monkeypatch.setattr(summary, "measure",
                        lambda _d: found(rows=[{"label": "a", "meta": {}}]))
    text = summary.render(tmp_path)
    warning = "아직 종료되지 않았다"
    assert warning in text
    assert text.index(warning) < text.index("사전 예측 여덟 개")


def test_a_finished_batch_carries_no_such_warning(tmp_path, monkeypatch):
    rows = [{"label": f"s{i}", "meta": {}}
            for i in range(summary.EXPECTED_SESSIONS)]
    monkeypatch.setattr(summary, "measure", lambda _d: found(rows=rows))
    assert "아직 종료되지 않았다" not in summary.render(tmp_path)


# ------------------------- 예측 7 — 정리 신호를 받고 인계 문서를 쓰는가

def test_prediction_seven_counts_sessions_that_wrote_a_handoff():
    """정리 신호가 통하는지를 본다. 인계가 안 남으면 예측 3·4·5의 판정이
    전부 흔들리므로, 이것이 빗나가면 배치를 중단한다."""
    wrote = {f"s{i:02d}": True for i in range(63)}
    wrote.update({f"x{i:02d}": False for i in range(7)})
    assert summary.predictions(found(written=wrote))[6]["hit"] is True

    one_short = {f"s{i:02d}": True for i in range(62)}
    one_short.update({f"x{i:02d}": False for i in range(8)})
    assert summary.predictions(found(written=one_short))[6]["hit"] is False


def test_prediction_seven_is_undecidable_with_no_sessions():
    assert summary.predictions(found())[6]["hit"] is None


# --------------- 예측 8 — 종료 메시지에서 예산을 이유로 드는가

def test_prediction_eight_counts_sessions_that_blamed_the_budget():
    """**이 배치의 세션별 성과를 능력 차이로 읽어도 되는지를 가르는 값이다.**

    세션이 남은 호출 수를 보고 일을 조절하면 멈추는 자리를 측정 대상이
    정하게 되고, 그러면 "몇 개를 했는가"가 능력이 아니라 우리 장치를 잰
    값이 된다.
    """
    clean = [session(f"s{i:02d}", "Finished subsystem A. Handoff updated.")
             for i in range(10)]
    assert summary.predictions(found(rows=clean))[7]["hit"] is True

    blamed = clean[:6] + [
        session("s06", "I'm over the session's tool-call budget (34/30)."),
        session("s07", "With 2 tool calls left in this session's budget."),
        session("s08", "stopping here at the budget warning."),
        session("s09", "Given the budget is now over its limit, I'm stopping."),
    ]
    assert summary.predictions(found(rows=blamed))[7]["hit"] is False


def test_the_budget_words_catch_every_phrasing_the_calibration_produced():
    """**낱말 하나로는 못 센다.**

    아래 문장들은 2026-08-21 보정 사슬 1차의 세션 종료 메시지에서 글자 그대로
    옮긴 것이다(원자료 `results/calib/subsystems-deep`, gitignore 대상이라
    CI 에 없으므로 여기 옮겨 적는다). 여덟 세션이 서로 다른 말로 같은 것을
    말했다.
    """
    said = [
        "With 2 tool calls left in this session's budget, I'll stop here "
        "rather than risk starting an edit I can't finish.",
        "Given the session's tool-call budget is now over its limit, I'm "
        "stopping here rather than starting new edits.",
        "I'm over the session's tool-call budget (34/30), so I'm stopping "
        "here without further edits.",
        "I stopped after these items due to a session tool-call budget "
        "warning, prioritizing writing a thorough handoff.",
        "Made progress on the v0.3 release under tight tool-call budget "
        "(a session-budget hook flagged remaining calls partway through).",
        "I'm at the last available tool call for this session, so I'll stop "
        "here with the handoff in good shape.",
        "HANDOFF.md is updated with what's done. That's the last write "
        "needed - stopping here at the budget warning.",
    ]
    rows = [session(f"s{i:02d}", text) for i, text in enumerate(said)]
    assert summary.budget_mentions(rows) == [r["label"] for r in rows], (
        "보정 1차에서 실제로 나온 표현을 못 잡는다")


def test_the_budget_words_do_not_fire_on_ordinary_wrap_up_messages():
    """**보정 2차의 여덟 세션은 하나도 걸리지 않아야 한다.**

    아래는 그 배치의 종료 메시지에서 옮긴 것이다. 여기서 하나라도 걸리면
    예측 8이 조건과 무관하게 빗나가고, 훅 수정이 통했는지 알 수 없게 된다.
    """
    quiet = [
        "This session finished subsystem A of the opsbox v0.3 release: fixed "
        "the three ingest bugs, verified all six sources now match.",
        "All 20 tests still pass. This session finished subsystem C (alerts).",
        "All tests pass, and HANDOFF.md is updated as instructed.",
        "v0.3 is fully done and I've independently confirmed it - no code "
        "changes needed this session.",
        "I've wrapped up this session's work on the v0.3 release.",
    ]
    rows = [session(f"s{i:02d}", text) for i, text in enumerate(quiet)]
    assert summary.budget_mentions(rows) == []
