"""읽기 지표를 배치 자료에 적용하는 도구 테스트 (`pilot/analysis/read_signal_check.py`).

이 파일이 못 박는 것은 셋이다.

1. **사슬의 첫 세션만 모은다.** 뒤 세션은 앞사람이 남긴 상태에서 시작하므로
   시작 상태가 같지 않다.
2. **값이 없는 세션을 0으로 세지 않는다.** 아무것도 안 고친 세션의
   `read_before_edit_ratio` 는 0이 아니라 잴 것이 없는 것이다. 0으로 세면
   "안 고친 세션" 과 "고쳤는데 안 읽고 고친 세션" 이 한 칸에 들어간다.
3. **구분됐다는 판정은 두 라벨 집단의 값 범위가 겹치지 않을 때만 나온다.**
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


check = _load("casa_read_signal_check",
              ROOT / "pilot" / "analysis" / "read_signal_check.py")


def _write(out_dir: Path, label: str, index: int, passed: int,
           calls: list[tuple[str, str]], task: str = "t") -> None:
    checks = {f"item.{i}": (i < passed) for i in range(10)}
    (out_dir / f"session-{label}.json").write_text(json.dumps({
        "task": task, "label": label, "session_index": index,
        "grade": {"checkpoints": checks},
    }), encoding="utf-8")
    lines = []
    for i, (name, path) in enumerate(calls):
        payload = {"file_path": path}
        if name in ("Edit", "Write"):
            payload = {"file_path": path, "old_string": "x", "new_string": "y"}
        lines.append(json.dumps({
            "type": "assistant",
            "message": {"content": [
                {"type": "tool_use", "id": f"u{i}", "name": name,
                 "input": payload}]},
        }))
    (out_dir / f"transcript-{label}.jsonl").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")


# ------------------------------------------------------ 무엇을 모으는가


def test_only_first_sessions_are_collected(tmp_path):
    _write(tmp_path, "c01s01", 1, 3, [("Read", "a.py")])
    _write(tmp_path, "c01s02", 2, 5, [("Read", "b.py")])
    rows = check.first_sessions(tmp_path)
    assert [r["label"] for r in rows] == ["c01s01"]


def test_a_session_without_a_transcript_is_skipped(tmp_path):
    _write(tmp_path, "c01s01", 1, 3, [("Read", "a.py")])
    (tmp_path / "transcript-c01s01.jsonl").unlink()
    assert check.first_sessions(tmp_path) == []


def test_advanced_is_decided_against_the_start_state(tmp_path):
    """세 과제 다 시작 상태에서 통과해 있는 항목이 하나다."""
    _write(tmp_path, "c01s01", 1, check.START_MARK, [("Read", "a.py")])
    _write(tmp_path, "c02s01", 1, check.START_MARK + 1, [("Read", "a.py")])
    got = {r["label"]: r["advanced"] for r in check.first_sessions(tmp_path)}
    assert got == {"c01s01": False, "c02s01": True}


def test_a_broken_session_file_does_not_stop_the_run(tmp_path):
    """이 출력은 판마다 다르다 — 못 읽는 줄은 건너뛴다."""
    _write(tmp_path, "c01s01", 1, 3, [("Read", "a.py")])
    (tmp_path / "session-bad.json").write_text("not json", encoding="utf-8")
    assert [r["label"] for r in check.first_sessions(tmp_path)] == ["c01s01"]


# --------------------------------------------------------- 잘라 보기


def test_head_keeps_only_the_early_calls(tmp_path):
    _write(tmp_path, "c01s01", 1, 3,
           [("Read", f"f{i}.py") for i in range(10)])
    from casa.transcript import parse
    session = parse(tmp_path / "transcript-c01s01.jsonl")
    assert len(check.head(session, 4).tool_calls) == 4


def test_head_drops_the_final_message(tmp_path):
    """마지막 메시지를 남기면 거기서 계산되는 지표에 정답이 새어 든다."""
    _write(tmp_path, "c01s01", 1, 3, [("Read", "a.py")])
    from casa.transcript import parse
    session = parse(tmp_path / "transcript-c01s01.jsonl")
    session.final_assistant_text = "All tests pass."
    assert check.head(session, 5).final_assistant_text is None


# --------------------------------------------- 두 라벨 집단의 값


def test_split_drops_sessions_whose_value_is_missing():
    measured = [{"advanced": True, "x": 0.5},
                {"advanced": True, "x": None},
                {"advanced": False, "x": None}]
    got = check.split(measured, "x")
    assert got["advanced"] == [0.5]
    assert got["flat"] == []
    assert got["separated"] is False


def test_split_counts_true_as_one_and_false_as_zero():
    measured = [{"advanced": True, "x": True}, {"advanced": False, "x": False}]
    got = check.split(measured, "x")
    assert got["advanced"] == [1.0] and got["flat"] == [0.0]
    assert got["separated"] is True


def test_separated_needs_the_two_ranges_not_to_overlap():
    overlap = [{"advanced": True, "x": 1}, {"advanced": True, "x": 5},
               {"advanced": False, "x": 3}]
    assert check.split(overlap, "x")["separated"] is False
    apart = [{"advanced": True, "x": 4}, {"advanced": True, "x": 5},
             {"advanced": False, "x": 1}]
    assert check.split(apart, "x")["separated"] is True


def test_separated_is_false_when_one_side_is_empty():
    only_up = [{"advanced": True, "x": 4}]
    assert check.split(only_up, "x")["separated"] is False


# ----------------------------------------------------------- 보고문


def test_report_says_when_a_task_has_only_one_side(tmp_path):
    _write(tmp_path, "c01s01", 1, 5, [("Read", "a.py")])
    _write(tmp_path, "c02s01", 1, 6, [("Read", "b.py")])
    out = check.report([tmp_path], windows=(5,))
    assert "구분할 것이 없다" in out


def test_report_puts_the_two_sides_in_a_table(tmp_path):
    _write(tmp_path, "c01s01", 1, 5,
           [("Read", "docs/plan.md"), ("Edit", "a.py"), ("Read", "docs/plan.md")])
    _write(tmp_path, "c02s01", 1, check.START_MARK, [("Read", "a.py")])
    out = check.report([tmp_path], windows=(5,))
    assert "`docs_after_first_edit`" in out
    assert "| 지표 | 항목을 늘린 세션 | 늘리지 못한 세션 | 구분되나 |" in out


def _meta(out_dir: Path, budget: int, task: str = "t") -> None:
    (out_dir / "meta.json").write_text(
        json.dumps({"task": task, "budget": budget}), encoding="utf-8")


# ------------------------------- 예산에 견준 자리로 판정하기


def test_budget_comes_from_the_batch_metadata(tmp_path):
    _meta(tmp_path, 30)
    assert check.batch_budget(tmp_path) == 30


def test_budget_is_none_when_the_metadata_is_missing_or_broken(tmp_path):
    assert check.batch_budget(tmp_path) is None
    (tmp_path / "meta.json").write_text("not json", encoding="utf-8")
    assert check.batch_budget(tmp_path) is None


def test_budget_is_none_when_the_value_is_not_a_positive_count(tmp_path):
    (tmp_path / "meta.json").write_text(json.dumps({"budget": 0}), encoding="utf-8")
    assert check.batch_budget(tmp_path) is None


def test_the_budget_is_carried_onto_every_row(tmp_path):
    _meta(tmp_path, 30)
    _write(tmp_path, "c01s01", 1, 3, [("Read", "a.py")])
    assert check.first_sessions(tmp_path)[0]["budget"] == 30


def test_guess_looks_only_at_calls_before_the_decision_point(tmp_path):
    """예산 10의 50% 지점은 5호출이다. 여섯째 호출의 고침은 안 보인다."""
    _meta(tmp_path, 10)
    calls = [("Read", f"f{i}.py") for i in range(5)] + [("Edit", "a.py")]
    _write(tmp_path, "c01s01", 1, 3, calls)
    row = check.first_sessions(tmp_path)[0]
    assert check.guess_at(row, 0.5) is False
    assert check.guess_at(row, 0.9) is True


def test_guess_is_none_without_a_budget(tmp_path):
    _write(tmp_path, "c01s01", 1, 3, [("Edit", "a.py")])
    assert check.guess_at(check.first_sessions(tmp_path)[0], 0.5) is None


def test_majority_rate_is_the_bigger_side():
    rows = [{"advanced": True}, {"advanced": False}, {"advanced": False}]
    assert check.majority_rate(rows) == 2 / 3
    assert check.majority_rate([]) == 0.0


def test_position_scan_reports_the_majority_baseline_next_to_the_hits(tmp_path):
    """관측이 필요 없는 값을 넘지 못하면 그 지표는 쓸모가 없다."""
    _meta(tmp_path, 10)
    _write(tmp_path, "c01s01", 1, 5, [("Edit", "a.py")] + [("Read", "b.py")] * 9)
    _write(tmp_path, "c02s01", 1, check.START_MARK, [("Read", "b.py")] * 10)
    out = check.position_scan(check.first_sessions(tmp_path), fractions=(0.5,))
    assert "많은 쪽 라벨로 전부 예측하면 50%" in out
    assert "| 예산의 50% | 2/2 |" in out


def test_position_scan_says_when_it_could_not_judge(tmp_path):
    _write(tmp_path, "c01s01", 1, 5, [("Edit", "a.py")])
    out = check.position_scan(check.first_sessions(tmp_path), fractions=(0.5,))
    assert "판정 못 함" in out


def test_detail_separates_never_edited_from_edited_late(tmp_path):
    """`docs_after_first_edit` 이 0인 것에 두 가지가 섞여 있다."""
    _write(tmp_path, "c01s01", 1, 5, [("Read", "a.py"), ("Edit", "a.py")])
    _write(tmp_path, "c02s01", 1, 5, [("Read", "a.py"), ("Read", "b.py")])
    out = check.detail([tmp_path])
    rows = [line for line in out.splitlines() if line.startswith("| t |")]
    assert len(rows) == 2
    assert any("| 1 | 0 |" in r for r in rows)      # 두 번째 호출에서 고쳤다
    assert any("| 없음 | 0 |" in r for r in rows)   # 아무것도 안 고쳤다
