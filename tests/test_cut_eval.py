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
