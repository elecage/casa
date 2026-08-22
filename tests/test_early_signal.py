"""초반 신호 분석 도구 테스트 (`pilot/analysis/early_signal.py`).

이 파일이 못 박는 것은 **정직한 판정 절차**다.

1. 문턱을 정한 자료와 판정하는 자료가 갈려 있다. 사슬 단위로 가른다 — 같은
   사슬의 세션들은 앞사람이 남긴 상태를 물려받으므로 서로 독립이 아니다.
2. 비교 대상(아무것도 안 보고 찍기, 세션 번호만 보기)이 같이 나온다.
3. 늘렸는가는 **앞 세션과 견주어** 정한다. 절대값으로 정하면 앞사람이 다 해 둔
   세션이 전부 "잘한 세션"이 된다.
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


early = _load("casa_early_signal", ROOT / "pilot" / "analysis" / "early_signal.py")


def _write_session(out_dir: Path, label: str, index: int, passed: int,
                   calls: list[tuple[str, str]]) -> None:
    """세션 기록과 트랜스크립트를 한 벌 만든다."""
    checks = {f"item.{i}": (i < passed) for i in range(early.FULL_MARK)}
    (out_dir / f"session-{label}.json").write_text(json.dumps({
        "label": label, "session_index": index,
        "grade": {"checkpoints": checks},
        "cli": {"total_cost_usd": 1.0}, "wall_s": 60,
        "audit": {"metrics": {"n_tool_calls": len(calls)}},
    }), encoding="utf-8")
    lines = []
    for name, path in calls:
        lines.append(json.dumps({
            "type": "assistant",
            "message": {"content": [
                {"type": "tool_use", "name": name, "input": {"file_path": path}}]},
        }))
    (out_dir / f"transcript-{label}.jsonl").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")


# ------------------------------------------- 트랜스크립트를 견디며 읽는다

def test_unknown_lines_are_skipped_not_fatal(tmp_path):
    """이 JSONL 은 문서화되어 있지 않고 판마다 다르다."""
    path = tmp_path / "t.jsonl"
    path.write_text('not json\n{}\n{"message": 3}\n'
                    '{"type":"assistant","message":{"content":'
                    '[{"type":"tool_use","name":"Read","input":{"file_path":"a.py"}}]}}\n',
                    encoding="utf-8")
    assert [c["name"] for c in early.tool_calls(path)] == ["Read"]


def test_a_missing_transcript_is_not_fatal(tmp_path):
    assert early.tool_calls(tmp_path / "nope.jsonl") == []


def test_the_target_of_a_call_falls_back_across_keys():
    assert early.target_of({"input": {"command": "python -m opsbox"}}) \
        == "python -m opsbox"
    assert early.target_of({"input": {}}) == ""


# ----------------------------------- 늘렸는가는 앞 세션과 견주어 정한다

def test_advancing_is_measured_against_the_previous_session(tmp_path):
    """절대값으로 정하면 앞사람이 다 해 둔 세션이 전부 잘한 세션이 된다."""
    _write_session(tmp_path, "c01s01", 1, 5, [("Read", "a.py")])
    _write_session(tmp_path, "c01s02", 2, 5, [("Read", "a.py")])
    _write_session(tmp_path, "c01s03", 3, 9, [("Read", "a.py")])

    rows = {r["label"]: r for r in early.sessions(tmp_path, 10)}
    assert rows["c01s01"]["advanced"] is True      # 1 -> 5
    assert rows["c01s02"]["advanced"] is False     # 5 -> 5
    assert rows["c01s03"]["advanced"] is True      # 5 -> 9


def test_a_session_that_starts_at_full_marks_is_flagged_as_having_no_work(tmp_path):
    """늘릴 것이 없어서 못 늘린 세션을 '못 한 세션'으로 세면 안 된다."""
    _write_session(tmp_path, "c01s01", 1, early.FULL_MARK, [("Read", "a.py")])
    _write_session(tmp_path, "c01s02", 2, early.FULL_MARK, [("Read", "a.py")])
    rows = {r["label"]: r for r in early.sessions(tmp_path, 10)}
    assert rows["c01s01"]["has_work_left"] is True
    assert rows["c01s02"]["has_work_left"] is False


# --------------------------------------- 문턱을 정한 자료로 판정하지 않는다

def test_the_threshold_is_chosen_without_the_chain_it_is_judged_on(tmp_path):
    """뺀 사슬이 훈련 자료에 들어가면 맞을 수밖에 없다.

    사슬 하나만 신호가 뒤집혀 있는 자료를 만든다. 뺀 사슬로 문턱을 정하면
    그 사슬도 맞히지만, 정직하게 가르면 못 맞힌다.
    """
    rows = []
    for chain in range(9):                       # 아홉 사슬: 값이 크면 늘린다
        rows.append({"chain": f"c{chain:02d}", "index": 1, "code": 5,
                     "advanced": True})
        rows.append({"chain": f"c{chain:02d}", "index": 2, "code": 0,
                     "advanced": False})
    rows.append({"chain": "c09", "index": 1, "code": 5, "advanced": False})
    rows.append({"chain": "c09", "index": 2, "code": 0, "advanced": True})

    accuracy = early.held_out_accuracy(
        rows, early.threshold_fit("code"), early.threshold_guess("code"))
    assert accuracy == 18 / 20, accuracy      # 뒤집힌 사슬 둘만 틀린다


def test_held_out_accuracy_needs_more_than_one_chain():
    rows = [{"chain": "c01", "index": 1, "code": 1, "advanced": True}]
    assert early.held_out_accuracy(
        rows, early.threshold_fit("code"),
        early.threshold_guess("code")) != early.held_out_accuracy(
        rows, early.threshold_fit("code"), early.threshold_guess("code")), (
        "사슬이 하나면 판정할 수 없다 — NaN 이어야 한다")


def test_the_threshold_search_prefers_the_smaller_of_equal_scores():
    """같은 점수의 문턱이 여럿이면 결과가 문턱 고르기의 우연에 흔들린다."""
    train = [{"code": 0, "advanced": False}, {"code": 3, "advanced": True},
             {"code": 7, "advanced": True}]
    assert early.threshold_fit("code")(train) == 3


# ------------------------------------------- 비교 대상이 같이 나온다

def test_the_report_carries_both_baselines(tmp_path):
    """관측이 필요 없는 값을 못 이기는 신호는 쓸모가 없다. 그것을 읽는 사람이
    바로 볼 수 있어야 한다."""
    for chain in range(2):
        for index in range(1, 4):
            _write_session(tmp_path, f"c{chain:02d}s{index:02d}", index,
                           1 + index, [("Read", "a.py")])
    text = early.report(tmp_path, windows=(10,))
    assert "아무것도 안 보고 다수 쪽" in text
    assert "세션 번호만" in text


def test_majority_falls_back_when_there_is_nothing_to_count():
    assert early.majority([]) is True


# --------------------------------------------------- 뒤섞어 보기

def test_shuffling_a_real_difference_rarely_reproduces_it():
    rows = ([{"code": 5, "advanced": True} for _ in range(20)]
            + [{"code": 0, "advanced": False} for _ in range(20)])
    assert early.shuffle_test(rows, "code", 1, rounds=2000) < 0.01


def test_shuffling_no_difference_reproduces_it_often():
    rows = ([{"code": 5, "advanced": i % 2 == 0} for i in range(20)]
            + [{"code": 0, "advanced": i % 2 == 0} for i in range(20)])
    assert early.shuffle_test(rows, "code", 1, rounds=2000) > 0.2


def test_shuffling_needs_both_sides():
    rows = [{"code": 5, "advanced": True} for _ in range(4)]
    got = early.shuffle_test(rows, "code", 1, rounds=10)
    assert got != got, "한쪽이 비면 판정할 수 없다 — NaN 이어야 한다"
