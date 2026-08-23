"""끊는 배치의 1차 지표 도구 테스트 (`pilot/analysis/cut_eval.py`).

이 파일이 못 박는 것 넷.

1. **관측 단위가 깃발이 선 자리다.** 사슬 끝 상태가 아니다 — 사슬 단위로는
   예상 차이(0.6항목)가 표준편차(4.8)에 묻힌다.
2. **두 갈래가 같은 판정으로 깃발을 센다.** 끊는 쪽은 러너가 적어 둔 것을,
   안 끊는 쪽은 트랜스크립트에서 같은 판정을 다시 낸 것을 쓴다.
3. **끊는 쪽의 성과는 끊긴 세션이 아니라 그 자리를 이어받은 세션의 것이다.**
   그리고 쓴 호출은 둘을 합친 것이다.
4. **교체 세션의 결과가 분포로 남는다.** 평균만 적으면 더 나쁜 세션이 들어온
   경우가 안 보인다.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


evaluate = _load("casa_cut_eval", ROOT / "pilot" / "analysis" / "cut_eval.py")


def _grade(passing: int, total: int = 58) -> dict:
    checks = {f"item.{i}": (i < passing) for i in range(total)}
    return {"task": "shared-core", "checkpoints": checks}


def _row(chain: int, index: int, passing: int, calls: int, *,
         cut: bool = False, transcript: Path | None = None) -> dict:
    return {
        "chain": chain, "session_index": index, "cut": cut,
        "grade": _grade(passing),
        "audit": {"metrics": {"n_tool_calls": calls}},
        "transcript": str(transcript) if transcript else None,
    }


def _transcript(path: Path, paths: list[str]) -> Path:
    lines = [json.dumps({
        "type": "assistant",
        "message": {"content": [{"type": "tool_use", "name": "Read",
                                 "input": {"file_path": p}}]}})
        for p in paths]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# ------------------------------------------------ 통과 항목과 성과

def test_passing_items_are_counted_from_the_checkpoints():
    assert evaluate.passed(_row(1, 1, 7, 20)) == 7


def test_an_ungradeable_session_is_not_counted_as_zero():
    """채점을 못 읽은 것과 0을 얻은 것은 다르다."""
    row = _row(1, 1, 7, 20)
    row["grade"] = {"parse_error": True}
    assert evaluate.passed(row) is None


# ------------------------------------------------------ 깃발 판정

def test_the_cut_arm_uses_what_the_runner_recorded(tmp_path):
    """훅이 실제로 끊었으면 깃발이 선 것이다. 트랜스크립트를 다시 안 본다."""
    row = _row(1, 2, 5, 10, cut=True)
    assert evaluate.flagged(row) is True


def test_the_keep_arm_judges_the_same_thing_from_the_transcript(tmp_path):
    never = _row(1, 1, 5, 30,
                 transcript=_transcript(tmp_path / "a.jsonl",
                                        ["docs/ingest.md"] * 30))
    opened = _row(1, 2, 9, 30,
                  transcript=_transcript(
                      tmp_path / "b.jsonl",
                      ["docs/a.md"] * 9 + ["core/months.py"] + ["x.md"] * 20))
    assert evaluate.flagged(never) is True
    assert evaluate.flagged(opened) is False


def test_a_session_too_short_to_judge_is_not_called_flagged(tmp_path):
    """열 호출이 안 되면 판정 불가다. 거짓이 아니다."""
    row = _row(1, 1, 5, 3,
               transcript=_transcript(tmp_path / "c.jsonl", ["docs/a.md"] * 3))
    assert evaluate.flagged(row) is None


# ------------------------------- 끊는 쪽의 성과는 이어받은 세션의 것

def test_the_gain_at_a_cut_seam_belongs_to_the_replacement():
    rows = [
        _row(1, 1, 10, 40),                 # 앞 세션
        _row(1, 2, 10, 10, cut=True),       # 끊겼다. 올린 것 없음
        _row(1, 3, 18, 40),                 # 이어받은 세션이 8을 올렸다
    ]
    marks = evaluate._with_replacements(rows, at=10, start=1)
    cut_marks = [m for m in marks if m["cut"]]
    assert len(cut_marks) == 1
    assert cut_marks[0]["gain"] == 0
    assert cut_marks[0]["replacement"]["gain"] == 8
    assert cut_marks[0]["replacement"]["calls"] == 40


def test_the_calls_spent_at_a_cut_seam_include_the_wasted_ones():
    """열 호출을 버린 값이 셈에 들어가야 한다."""
    rows = [
        _row(1, 1, 10, 40),
        _row(1, 2, 10, 10, cut=True),
        _row(1, 3, 18, 40),
    ]
    side = evaluate.arm_summary([rows], at=10, start=1)
    assert side["judged"] == 1
    # 8항목을 50호출(버린 10 + 쓴 40)에 얻었다.
    assert side["gain_per_call"][0] == 8 / 50


def test_a_cut_at_the_end_of_a_chain_is_not_judged():
    """이어받은 세션이 없으면 끊기의 값을 셀 수 없다."""
    rows = [_row(1, 1, 10, 40), _row(1, 2, 10, 10, cut=True)]
    side = evaluate.arm_summary([rows], at=10, start=1)
    assert side["occurrences"] == 1
    assert side["judged"] == 0


def test_the_keep_arm_uses_the_flagged_session_itself(tmp_path):
    rows = [
        _row(1, 1, 10, 40,
             transcript=_transcript(tmp_path / "k1.jsonl",
                                    ["docs/a.md"] * 9 + ["core/months.py"])),
        _row(1, 2, 12, 40,
             transcript=_transcript(tmp_path / "k2.jsonl",
                                    ["docs/a.md"] * 40)),
    ]
    side = evaluate.arm_summary([rows], at=10, start=1)
    assert side["occurrences"] == 1
    assert side["gain_per_call"][0] == 2 / 40


# ---------------------------------------- 교체 세션의 결과는 분포로

def test_the_replacement_outcomes_are_reported_as_a_spread():
    """평균만 적으면 더 나쁜 세션이 들어온 경우가 안 보인다."""
    worse = [_row(1, 1, 10, 40), _row(1, 2, 10, 10, cut=True),
             _row(1, 3, 11, 40)]          # 1을 올렸다
    better = [_row(2, 1, 10, 40), _row(2, 2, 10, 10, cut=True),
              _row(2, 3, 20, 40)]         # 10을 올렸다
    same = [_row(3, 1, 10, 40), _row(3, 2, 10, 10, cut=True),
            _row(3, 3, 14, 40)]           # 4를 올렸다

    spread = evaluate.replacement_spread([worse, better, same],
                                         keep_gains=[4], at=10, start=1)
    assert spread["replacements"] == [1, 4, 10]
    assert spread["baseline"] == 4
    assert (spread["worse"], spread["same"], spread["better"]) == (1, 1, 1)


def test_the_spread_survives_having_no_keep_side_to_compare_with():
    rows = [_row(1, 1, 10, 40), _row(1, 2, 10, 10, cut=True),
            _row(1, 3, 12, 40)]
    spread = evaluate.replacement_spread([rows], keep_gains=[], at=10, start=1)
    assert spread["replacements"] == [2]
    assert spread["baseline"] is None


# ------------------------------------------------------- 읽고 쓰기

def test_the_arm_is_read_from_the_session_files(tmp_path):
    for index, passing in ((1, 5), (2, 9)):
        (tmp_path / f"session-c01s{index:02d}.json").write_text(
            json.dumps(_row(1, index, passing, 30)), encoding="utf-8")
    (tmp_path / "session-c02s01.json").write_text(
        json.dumps(_row(2, 1, 4, 30)), encoding="utf-8")

    chains = evaluate.load_arm(tmp_path)
    assert [len(rows) for rows in chains] == [2, 1]
    assert evaluate.passed(chains[0][1]) == 9


# ------------------------------- 봉인한 예측이 코드에 박혀 있다

def test_the_sealed_thresholds_are_pinned():
    """문턱이 바뀌면 여기서 깨진다. 결과를 본 뒤에 문턱을 옮기면 안 된다."""
    assert evaluate.MIN_OCCURRENCES == 8
    assert evaluate.CUT_RATE_RANGE == (0.10, 0.35)
    assert evaluate.DEFAULT_AT == 10


def test_too_few_occurrences_is_reported_as_undecided_not_as_no_difference():
    """관측이 모자라면 '차이 없음'이 아니라 '판정하지 못함'이다."""
    keep = [[_row(1, 1, 10, 40), _row(1, 2, 12, 40)]]
    cut = [[_row(2, 1, 10, 40), _row(2, 2, 10, 10, cut=True),
            _row(2, 3, 18, 40)]]
    result = {"keep": evaluate.arm_summary(keep, 10, 1),
              "cut": evaluate.arm_summary(cut, 10, 1),
              "replacement_spread": evaluate.replacement_spread(
                  cut, [], 10, 1)}
    checks = evaluate.check_predictions(result, keep, cut, start=1)
    floor = next(c for c in checks if c["prediction"] == 0)
    assert floor["held"] is None


def test_the_cut_rate_prediction_uses_the_pinned_range():
    # 세 세션 중 하나가 끊겼다 = 33%, 범위 안이다.
    cut = [[_row(1, 1, 10, 40), _row(1, 2, 10, 10, cut=True),
            _row(1, 3, 18, 40)]]
    assert evaluate.cut_rate(cut) == 1 / 3
    result = {"keep": evaluate.arm_summary([], 10, 1),
              "cut": evaluate.arm_summary(cut, 10, 1),
              "replacement_spread": evaluate.replacement_spread(
                  cut, [], 10, 1)}
    three = next(c for c in evaluate.check_predictions(result, [], cut, 1)
                 if c["prediction"] == 3)
    assert three["held"] is True


def test_a_cut_that_lost_items_fails_prediction_five():
    """열 호출 안의 편집이 반쯤 된 채 끊기면 항목이 줄 수 있다."""
    kept = [[_row(1, 1, 10, 40), _row(1, 2, 10, 10, cut=True),
             _row(1, 3, 18, 40)]]
    assert evaluate.cut_sessions_lost_nothing(kept, start=1) is True

    lost = [[_row(1, 1, 10, 40), _row(1, 2, 7, 10, cut=True),
             _row(1, 3, 18, 40)]]
    assert evaluate.cut_sessions_lost_nothing(lost, start=1) is False


def test_missed_predictions_are_rendered_first():
    result = {"at": 10, "start_state": 1,
              "keep": {"occurrences": 9, "judged": 9, "gain_per_call": [],
                       "gain_per_call_median": 0.05, "gains": [2],
                       "gain_median": 2},
              "cut": {"occurrences": 9, "judged": 9, "gain_per_call": [],
                      "gain_per_call_median": 0.02, "gains": [1],
                      "gain_median": 1},
              "replacement_spread": {"replacements": [1], "baseline": 2,
                                     "worse": 1, "same": 0, "better": 0},
              "predictions": [
                  {"prediction": 0, "says": "관측이 넉넉하다", "held": True},
                  {"prediction": 1, "says": "끊는 쪽이 낫다", "held": False},
                  {"prediction": 2, "says": "세션이 더 돈다", "held": None},
              ]}
    body = evaluate.render(result)
    rows = [ln for ln in body.splitlines() if ln.startswith("| ")]
    table = [ln for ln in rows if "빗나감" in ln or "판정 불가" in ln
             or "맞음" in ln]
    assert "빗나감" in table[0]
    assert "판정 불가" in table[1]
    assert "맞음" in table[2]


# ------------------- 초반 신호가 새 자료에서도 서는가 (예측 7)

def test_the_two_groups_the_signal_splits_are_counted_separately(tmp_path):
    """깃발이 선 세션만 세면 신호가 재현되는지 판정할 수 없다."""
    rows = [
        # 깃발이 섰고(문서만 읽었다) 항목을 못 늘렸다
        _row(1, 1, 10, 40,
             transcript=_transcript(tmp_path / "s1.jsonl", ["docs/a.md"] * 40)),
        # 깃발이 안 섰고(코드를 열었다) 5를 늘렸다
        _row(1, 2, 15, 40,
             transcript=_transcript(tmp_path / "s2.jsonl",
                                    ["core/months.py"] + ["docs/a.md"] * 39)),
        # 깃발이 섰고 2를 늘렸다
        _row(1, 3, 17, 40,
             transcript=_transcript(tmp_path / "s3.jsonl", ["docs/b.md"] * 40)),
    ]
    split = evaluate.signal_split([rows], at=10, start=10)
    assert split["flagged"]["n"] == 2
    assert split["flagged"]["raised"] == 1
    assert split["flagged"]["rate"] == 0.5
    assert split["unflagged"]["n"] == 1
    assert split["unflagged"]["rate"] == 1.0


def test_a_session_whose_flag_cannot_be_judged_is_in_neither_group():
    """트랜스크립트를 못 읽으면 어느 무리에도 넣지 않는다. 0으로 세지 않는다."""
    split = evaluate.signal_split([[_row(1, 1, 10, 40)]], at=10, start=1)
    assert split["flagged"]["n"] == 0
    assert split["unflagged"]["n"] == 0


def _split_rows(tmp_path, flagged_gains, unflagged_gains):
    """지정한 성과대로 두 무리를 만든다. 세션마다 트랜스크립트가 따로 있다."""
    rows, passing, index = [], 1, 1
    for gains, opens_code in ((flagged_gains, False), (unflagged_gains, True)):
        for gain in gains:
            passing += gain
            paths = (["core/months.py"] if opens_code else []) \
                + ["docs/a.md"] * 40
            rows.append(_row(1, index, passing, 40,
                             transcript=_transcript(
                                 tmp_path / f"p{index}.jsonl", paths)))
            index += 1
    return rows


def test_prediction_seven_holds_when_the_unflagged_group_raises_more(tmp_path):
    rows = _split_rows(tmp_path, [0] * 8, [3] * 8)
    keep = [rows]
    result = {"keep": evaluate.arm_summary(keep, 10, 1),
              "cut": evaluate.arm_summary([], 10, 1),
              "replacement_spread": evaluate.replacement_spread([], [], 10, 1),
              "signal_split": evaluate.signal_split(keep, 10, 1)}
    seven = next(c for c in evaluate.check_predictions(result, keep, [], 1)
                 if c["prediction"] == 7)
    assert seven["held"] is True


def test_prediction_seven_is_missed_when_the_signal_does_not_separate(tmp_path):
    """깃발이 선 쪽이 더 잘하면 신호가 뒤집힌 것이고, 빗나감으로 적어야 한다."""
    rows = _split_rows(tmp_path, [3] * 8, [0] * 8)
    keep = [rows]
    result = {"keep": evaluate.arm_summary(keep, 10, 1),
              "cut": evaluate.arm_summary([], 10, 1),
              "replacement_spread": evaluate.replacement_spread([], [], 10, 1),
              "signal_split": evaluate.signal_split(keep, 10, 1)}
    seven = next(c for c in evaluate.check_predictions(result, keep, [], 1)
                 if c["prediction"] == 7)
    assert seven["held"] is False


def test_prediction_seven_is_undecided_below_the_observation_floor(tmp_path):
    """깃발이 관측 하한에 못 미치면 '차이 없음'이 아니라 '판정하지 못함'이다."""
    rows = _split_rows(tmp_path, [0] * 3, [3] * 8)
    keep = [rows]
    result = {"keep": evaluate.arm_summary(keep, 10, 1),
              "cut": evaluate.arm_summary([], 10, 1),
              "replacement_spread": evaluate.replacement_spread([], [], 10, 1),
              "signal_split": evaluate.signal_split(keep, 10, 1)}
    seven = next(c for c in evaluate.check_predictions(result, keep, [], 1)
                 if c["prediction"] == 7)
    assert seven["held"] is None


# ------------------- 세션마다 얼마를 늘렸는가 (서술 통계)

def test_the_gain_spread_splits_by_position_in_the_chain():
    """사슬 끝 상태에는 능력과 위치가 섞여 있다. 위치별로 갈라야 한다."""
    first = [_row(1, 1, 11, 40), _row(1, 2, 14, 40)]
    second = [_row(2, 1, 6, 40), _row(2, 2, 16, 40)]
    spread = evaluate.gain_spread([first, second], at=10, start=1)
    assert spread["by_position"] == {1: [5, 10], 2: [3, 10]}
    assert spread["all"] == [3, 5, 10, 10]
    assert spread["chain_end"] == [14, 16]


def test_a_cut_session_is_left_out_of_the_capability_spread():
    """우리가 도중에 끝낸 세션의 0은 관측이 아니다."""
    rows = [_row(1, 1, 11, 40), _row(1, 2, 11, 10, cut=True),
            _row(1, 3, 15, 40)]
    spread = evaluate.gain_spread([rows], at=10, start=1)
    assert spread["all"] == [4, 10]
    assert 2 not in spread["by_position"]


def test_the_spread_survives_a_single_session():
    """표준편차를 낼 수 없어도 도구가 멈추지 않는다."""
    spread = evaluate.gain_spread([[_row(1, 1, 11, 40)]], at=10, start=1)
    assert spread["all"] == [10]
    assert spread["sd"] is None


def test_the_two_side_records_are_rendered():
    result = {"at": 10, "start_state": 1,
              "keep": {"occurrences": 3, "judged": 3, "gain_per_call": [],
                       "gain_per_call_median": 0.05, "gains": [2],
                       "gain_median": 2},
              "cut": {"occurrences": 3, "judged": 3, "gain_per_call": [],
                      "gain_per_call_median": 0.08, "gains": [5],
                      "gain_median": 5},
              "replacement_spread": {"replacements": [5], "baseline": 2,
                                     "worse": 0, "same": 0, "better": 1},
              "signal_split": {
                  "flagged": {"n": 12, "raised": 4, "rate": 1 / 3,
                              "gains": [0]},
                  "unflagged": {"n": 20, "raised": 15, "rate": 0.75,
                                "gains": [3]}},
              "gain_spread": {"by_position": {1: [5, 10], 2: [3]},
                              "all": [3, 5, 10], "median": 5, "sd": 3.61,
                              "chain_end": [14, 16]}}
    text = evaluate.render(result)
    assert "33%" in text and "75%" in text
    assert "[3, 5, 10]" in text
    assert "[14, 16]" in text


def test_the_rendered_table_names_both_arms():
    result = {"at": 10, "start_state": 1,
              "keep": {"occurrences": 3, "judged": 3,
                       "gain_per_call": [], "gain_per_call_median": 0.05,
                       "gains": [2], "gain_median": 2},
              "cut": {"occurrences": 4, "judged": 3,
                      "gain_per_call": [], "gain_per_call_median": 0.08,
                      "gains": [5], "gain_median": 5},
              "replacement_spread": {"replacements": [1, 5, 9], "baseline": 2,
                                     "worse": 1, "same": 0, "better": 2}}
    text = evaluate.render(result)
    assert "안 끊는 쪽" in text and "끊는 쪽" in text
    assert "[1, 5, 9]" in text
    assert "낮음 1" in text and "높음 2" in text


# ------------------- 사슬이 이미 끝난 뒤의 자리 (2026-08-23 사후 분석)

def _plain_chain(scores: list[int], calls: int = 20) -> list[dict]:
    """통과 항목 수만 다른 세션 기록. 깃발 판정은 안 붙인다."""
    return [_row(1, index + 1, value, calls)
            for index, value in enumerate(scores)]


def test_plateau_index_finds_where_the_chain_stopped_gaining():
    # 세션 3에서 56에 도달하고 그 뒤로는 그대로다.
    rows = _plain_chain([19, 26, 56, 56, 56])
    assert evaluate.plateau_index(rows) == 2


def test_plateau_index_covers_a_chain_that_never_plateaus():
    rows = _plain_chain([10, 20, 30])
    assert evaluate.plateau_index(rows) == 2


def test_plateau_index_survives_an_unreadable_grade():
    assert evaluate.plateau_index([]) == 0
    assert evaluate.plateau_index([{"grade": None}]) == 1


def test_finished_early_counts_the_sessions_that_had_nothing_left():
    """사슬이 최종 항목 수에 도달한 뒤 실행된 세션을 센다.

    안 끊는 쪽 실제 자료에서 140세션 중 102개(73%)가 그런 세션이었고,
    봉인된 1차 지표가 그 자리들을 그대로 담고 있었다.
    """
    out = evaluate.finished_early([_plain_chain([19, 26, 56, 56, 56], calls=10)])
    assert out["reached_at"] == [3]
    assert out["sessions_after"] == 2
    assert out["calls_after"] == 20
    assert out["calls_total"] == 50


def test_live_gain_per_call_drops_the_positions_with_nothing_left(tmp_path):
    """이미 끝난 사슬의 자리는 어느 갈래든 성과가 0이라 견줄 수 없다."""
    # 초반 10호출에 `.py` 를 한 번도 안 열면 깃발이 선다.
    flagged = _transcript(tmp_path / "flag.jsonl",
                          ["README.md"] * 12)
    # 세션 2에서 이미 끝났고, 세션 3·4는 늘릴 것이 없다. 셋 다 깃발이 선다.
    rows = [_row(1, 1, 10, 20, transcript=flagged),
            _row(1, 2, 30, 20, transcript=flagged),
            _row(1, 3, 30, 20, transcript=flagged),
            _row(1, 4, 30, 20, transcript=flagged)]
    whole = evaluate.arm_summary([rows], start=1)
    live = evaluate.live_gain_per_call([rows], start=1)
    assert whole["judged"] == 4, "봉인된 지표는 네 자리를 다 담는다"
    assert live["judged"] == 2, "끝난 뒤의 두 자리는 빠져야 한다"
    # 성과가 0일 수밖에 없는 자리가 섞이면 중앙값이 그쪽으로 끌려간다.
    # 네 자리는 [0.45, 1.0, 0, 0] 이고 앞 두 자리만 남기면 [0.45, 1.0] 이다.
    assert whole["gain_per_call_median"] == 0.225
    assert live["gain_per_call_median"] == 0.725


def test_the_sealed_primary_metric_does_not_use_the_post_hoc_restriction():
    """사후 분석을 더한 것이 봉인된 1차 지표를 건드리면 안 된다."""
    source = (ROOT / "pilot" / "analysis" / "cut_eval.py").read_text(
        encoding="utf-8")
    body = source.split("def arm_summary", 1)[1].split("\ndef ", 1)[0]
    assert "plateau_index" not in body, "봉인된 지표가 사후 한정을 쓰고 있다"


# ------------- 통과하던 항목을 깨뜨렸는가 (2026-08-23, record-shape 프로브)

def _row_with(index: int, checks: dict) -> dict:
    return {"chain": 1, "session_index": index, "label": f"c01s{index:02d}",
            "grade": {"checkpoints": checks},
            "audit": {"metrics": {"n_tool_calls": 10}}}


def test_a_session_that_breaks_a_passing_item_is_recorded():
    """되돌리는 비용을 줄 수로만 세면 이 모양을 못 잡는다.

    사슬 프로브에서 세션 2가 세션 1이 통과시킨 항목 둘을 깨뜨렸는데 지운
    줄은 다섯 줄뿐이었다. 값은 지운 줄이 아니라 **깨진 채 남았다**는 데 있다.
    """
    rows = [
        _row_with(1, {"a": True, "b": True, "c": False}),
        _row_with(2, {"a": True, "b": False, "c": True}),
        _row_with(3, {"a": True, "b": False, "c": True}),
    ]
    history = evaluate.regressions(rows)
    assert history[0]["broke"] == []
    assert history[1]["broke"] == ["b"]
    assert history[1]["left_broken"] == ["b"]
    assert history[1]["repaired_at"] == {}


def test_a_broken_item_that_a_later_session_fixes_is_marked_repaired():
    rows = [
        _row_with(1, {"a": True}),
        _row_with(2, {"a": False}),
        _row_with(3, {"a": False}),
        _row_with(4, {"a": True}),
    ]
    history = evaluate.regressions(rows)
    assert history[1]["broke"] == ["a"]
    assert history[1]["repaired_at"] == {"a": 4}
    assert history[1]["left_broken"] == []


def test_an_item_that_never_passed_is_not_a_regression():
    """한 번도 통과한 적 없는 항목이 계속 안 통과하는 것은 깨뜨린 것이 아니다."""
    rows = [_row_with(1, {"a": False}), _row_with(2, {"a": False})]
    assert all(not entry["broke"] for entry in evaluate.regressions(rows))


def test_an_unjudged_item_counts_as_broken():
    """채점이 판정 불가로 바뀐 것도 통과 상태를 잃은 것이다."""
    rows = [_row_with(1, {"a": True}), _row_with(2, {"a": None})]
    assert evaluate.regressions(rows)[1]["broke"] == ["a"]


def test_the_regression_summary_counts_what_was_left_broken():
    rows = [
        _row_with(1, {"a": True, "b": True}),
        _row_with(2, {"a": False, "b": False}),
        _row_with(3, {"a": True, "b": False}),
    ]
    out = evaluate.regression_summary(rows)
    assert out["sessions_that_broke_something"] == 1
    assert out["broken_total"] == 2
    assert out["repaired"] == 1
    assert out["left_broken"] == 1 and out["left_broken_names"] == ["b"]


def test_the_regression_summary_survives_an_empty_chain():
    out = evaluate.regression_summary([])
    assert out["sessions"] == 0 and out["broken_total"] == 0
