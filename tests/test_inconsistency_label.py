"""심어 둔 어긋남에서 세션이 무엇을 했는지 세는 도구
(`pilot/analysis/inconsistency_label.py`).

이 파일이 못 박는 것 넷.

1. **두 쪽을 다 읽어야 그 자리를 지나간 것으로 센다.** 한쪽만 읽으면 아니다.
2. **확인은 두 쪽을 다 읽은 뒤에 온 것만 센다.** 읽기 전에 돌린 테스트는
   그 어긋남을 확인한 것이 아니다.
3. **경로는 끝으로 맞춘다.** 세션이 어느 디렉토리에서 부르든 같은 파일이다.
4. **물으며 끝냈는지는 보조 신호이고 결정론적인 값과 섞지 않는다.**
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


label = _load("casa_inconsistency_label",
              ROOT / "pilot" / "analysis" / "inconsistency_label.py")


def _transcript(path: Path, calls: list[tuple[str, str]], final: str = "") -> Path:
    lines = []
    for i, (name, target) in enumerate(calls):
        payload = ({"command": target} if name == "Bash"
                   else {"file_path": target})
        lines.append(json.dumps({
            "type": "assistant",
            "message": {"content": [{"type": "tool_use", "id": f"u{i}",
                                     "name": name, "input": payload}]}}))
    if final:
        lines.append(json.dumps({
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": final}]}}))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# ------------------------------------------------------- 경로 맞추기


def test_a_path_matches_by_its_tail():
    assert label._matches("/work/repo/CHANGELOG.md", "CHANGELOG.md")
    assert label._matches("CHANGELOG.md", "CHANGELOG.md")
    assert label._matches("repo/core/months.py", "core/months.py")


def test_a_longer_name_does_not_match_by_accident():
    assert not label._matches("docs/OLD_CHANGELOG.md", "CHANGELOG.md")
    assert not label._matches("core/months_test.py", "core/months.py")


def test_first_read_returns_the_earliest_call_that_hit_the_group():
    targets = [(0, "a.py"), (3, "CHANGELOG.md"), (7, "CHANGELOG.md")]
    assert label._first_read(targets, ["CHANGELOG.md"]) == 3
    assert label._first_read(targets, ["README.md"]) is None


# ------------------------------------------- 그 자리를 지나갔는가


def test_reading_only_one_side_is_not_passing_through(tmp_path):
    t = _transcript(tmp_path / "t.jsonl", [("Read", "CHANGELOG.md")])
    row = label.session_row(t)
    assert row["per"]["changelog-vs-code"]["passed_through"] is False


def test_reading_both_sides_is_passing_through(tmp_path):
    t = _transcript(tmp_path / "t.jsonl",
                    [("Read", "CHANGELOG.md"), ("Read", "billsy/reconcile.py")])
    row = label.session_row(t)
    assert row["per"]["changelog-vs-code"]["passed_through"] is True
    assert row["passed_through_n"] >= 1


# ------------------------------------------------- 확인의 차례


def test_a_check_before_reading_both_sides_does_not_count(tmp_path):
    """읽기 전에 돌린 테스트는 그 어긋남을 확인한 것이 아니다."""
    t = _transcript(tmp_path / "t.jsonl",
                    [("Bash", "python -m pytest"),
                     ("Read", "CHANGELOG.md"),
                     ("Read", "billsy/reconcile.py")])
    row = label.session_row(t)
    assert row["per"]["changelog-vs-code"]["passed_through"] is True
    assert row["per"]["changelog-vs-code"]["checked_after"] is False


def test_a_check_after_reading_both_sides_counts(tmp_path):
    t = _transcript(tmp_path / "t.jsonl",
                    [("Read", "CHANGELOG.md"),
                     ("Read", "billsy/reconcile.py"),
                     ("Bash", "python -m pytest")])
    row = label.session_row(t)
    assert row["per"]["changelog-vs-code"]["checked_after"] is True
    assert row["checked_n"] >= 1


# ----------------------------------------------- 인계 문서와 보조 신호


def test_touching_the_handoff_document_is_recorded(tmp_path):
    t = _transcript(tmp_path / "t.jsonl", [("Read", "HANDOFF.md")])
    assert label.session_row(t)["touched_handoff"] is False
    t2 = _transcript(tmp_path / "t2.jsonl",
                     [("Read", "HANDOFF.md"), ("Edit", "HANDOFF.md")])
    assert label.session_row(t2)["touched_handoff"] is True


def test_asking_is_read_from_the_final_message_only(tmp_path):
    """물었는지는 세션이 쓴 글에서 온다 — 결정론적이지 않으므로 따로 둔다."""
    quiet = _transcript(tmp_path / "a.jsonl", [("Read", "HANDOFF.md")],
                        final="Done, all items are checked off.")
    asking = _transcript(tmp_path / "b.jsonl", [("Read", "HANDOFF.md")],
                         final="Before diving in, I found a mismatch. "
                               "Do you want me to follow RELEASE.md?")
    assert label.session_row(quiet)["asked"] is False
    assert label.session_row(asking)["asked"] is True


def test_the_auxiliary_signal_does_not_change_the_deterministic_counts(tmp_path):
    calls = [("Read", "CHANGELOG.md"), ("Read", "billsy/reconcile.py")]
    quiet = _transcript(tmp_path / "a.jsonl", calls, final="All done.")
    asking = _transcript(tmp_path / "b.jsonl", calls,
                         final="Which did you mean?")
    a, b = label.session_row(quiet), label.session_row(asking)
    assert a["passed_through_n"] == b["passed_through_n"]
    assert a["checked_n"] == b["checked_n"]


# ------------------------------------------------------- 목록 자체


def test_every_planted_spot_names_two_sides():
    for item in label.INCONSISTENCIES:
        assert item["a"] and item["b"], item["key"]
        assert item["what"], item["key"]


def test_the_seven_spots_match_the_task_design():
    """`pilot/tasks/shared-core/DESIGN.md` 3절이 일곱 자리라고 적는다."""
    assert len(label.INCONSISTENCIES) == 7
    assert len({i["key"] for i in label.INCONSISTENCIES}) == 7
