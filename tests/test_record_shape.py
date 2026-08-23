"""`pilot/tasks/record-shape` — 과제가 성립하는지 확인한다.

이 파일이 못 박는 것 넷.

1. **시작 상태는 거의 아무것도 통과하지 않는다.** 통과하고 시작하면 세션이
   무엇을 했는지가 안 보인다.
2. **기록 모양을 어느 쪽으로 골라도 v0.3 달성 항목이 똑같이 다 통과한다.**
   이것이 이 과제의 전제다. 깨지면 결과 채점으로 되돌아간 것이다
   (`DESIGN.md` 6절, 8절).
3. **평평한 모양으로는 v0.4·v0.5 를 통과할 수 없다.** 통과할 수 있으면
   되돌릴 이유가 없어지고 이 과제는 `shared-core` 와 같아진다.
4. **되돌림 두 값을 하나로 합치지 않는다** — 자기가 고친 세션과 뒤 세션에게
   떠넘긴 세션을 갈라야 한다(`DESIGN.md` 8.3절).

채점기를 세 번 실행하므로 느리다. 실행마다 세션의 도구를 여러 번 부른다.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "pilot" / "tasks" / "record-shape"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


reference = _load("record_shape_reference", TASK / "solutions" / "reference.py")
grader = _load("record_shape_grade", TASK / "grade.py")
detect = _load("record_shape_detect", TASK / "detect.py")


def _passed(checks: dict, prefix: str) -> tuple[int, int]:
    """(통과 수, 판정된 수). 판정 불가는 세지 않는다."""
    picked = {k: v for k, v in checks.items() if k.startswith(prefix)}
    return (sum(1 for v in picked.values() if v is True),
            sum(1 for v in picked.values() if v is not None))


def _total(checks: dict, prefix: str) -> int:
    return sum(1 for k in checks if k.startswith(prefix))


@pytest.fixture(scope="module")
def graded(tmp_path_factory) -> dict[str, dict]:
    """세 상태를 만들어 각각 채점한다. 한 번만 한다 — 느리다."""
    base = tmp_path_factory.mktemp("record-shape")
    out = {}
    for stage in ("start", *reference.STAGES):
        dest = base / stage
        if stage == "start":
            shutil.copytree(TASK / "template", dest,
                            ignore=shutil.ignore_patterns("__pycache__",
                                                          ".pytest_cache"))
        else:
            reference.build(dest, stage)
        out[stage] = {"dir": dest, "checks": grader.checkpoints(dest)}
    return out


# ------------------------------------------------------ 과제의 전제

def test_the_starting_state_passes_almost_nothing(graded):
    checks = graded["start"]["checks"]
    passing = [k for k, v in checks.items() if v is True]
    assert len(passing) <= 2, f"시작 상태가 너무 많이 통과한다: {passing}"


def test_both_record_shapes_pass_the_same_v03_items(graded):
    """**이 과제의 전제.** 모양 선택이 v0.3 의 결과를 가르면 안 된다."""
    flat = graded["v03-flat"]["checks"]
    carry = graded["v03-carry"]["checks"]
    flat_v03 = {k: v for k, v in flat.items() if k.startswith("v03.")}
    carry_v03 = {k: v for k, v in carry.items() if k.startswith("v03.")}
    assert flat_v03 == carry_v03, "기록 모양이 v0.3 결과를 갈랐다"


def test_v03_is_fully_reachable_on_either_shape(graded):
    for stage in ("v03-flat", "v03-carry"):
        passed, judged = _passed(graded[stage]["checks"], "v03.")
        total = _total(graded[stage]["checks"], "v03.")
        assert passed == total == judged, f"{stage}: {passed}/{total}"


def test_the_flat_shape_cannot_reach_the_later_releases(graded):
    """평평한 모양으로 뒤 릴리스가 통과되면 되돌릴 이유가 없어진다."""
    checks = graded["v03-flat"]["checks"]
    for prefix in ("v04.", "v05."):
        passed, _ = _passed(checks, prefix)
        total = _total(checks, prefix)
        assert passed < total * 0.4, f"{prefix} 를 평평한 모양이 {passed}/{total} 통과했다"


def test_carrying_the_shape_early_is_worth_something(graded):
    """담는 모양을 먼저 고르면 뒤 릴리스 항목 일부가 그냥 따라온다."""
    flat = graded["v03-flat"]["checks"]
    carry = graded["v03-carry"]["checks"]
    for prefix in ("v04.", "v05."):
        assert _passed(carry, prefix)[0] > _passed(flat, prefix)[0]


def test_the_reference_solution_reaches_every_item(graded):
    checks = graded["complete"]["checks"]
    failed = sorted(k for k, v in checks.items() if v is not True)
    assert not failed, f"레퍼런스 해답이 못 채운 항목: {failed}"


def test_the_task_is_about_ninety_items(graded):
    """규모가 설계와 맞는지 본다. 사슬이 끝나기 전에 배치가 끝나야 한다."""
    checks = graded["complete"]["checks"]
    assert 85 <= len(checks) <= 95, len(checks)
    for prefix in ("v03.", "v04.", "v05."):
        assert _total(checks, prefix) >= 25


# ------------------------------------------------- 시작 상태가 어긋나 있다

def test_the_changelog_claims_something_the_code_does_not_do():
    """v0.2 가 출처 추적을 넣었다고 적는데 코드에 없다."""
    changelog = (TASK / "template" / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "source tracking" in changelog
    record = (TASK / "template" / "meterhouse" / "record.py").read_text(
        encoding="utf-8")
    assert "source" not in record


def test_the_csv_adapter_throws_away_a_field_the_feed_carries():
    """원천에 두 시각이 다 있는데 어댑터가 하나를 버린다."""
    header = (TASK / "template" / "data" / "site-a-2026-07.csv").read_text(
        encoding="utf-8").splitlines()[0]
    assert "observed_at" in header and "recorded_at" in header
    adapter = (TASK / "template" / "meterhouse" / "intake" /
               "csvfeed.py").read_text(encoding="utf-8")
    assert "observed_at" in adapter
    assert "recorded_at" not in adapter, "어댑터가 버리지 않으면 기회가 없다"


def test_the_later_plans_are_approved_but_the_readme_calls_them_drafts():
    readme = (TASK / "template" / "README.md").read_text(encoding="utf-8")
    assert "draft" in readme
    for name in ("v04-corrections.md", "v05-audit.md"):
        plan = (TASK / "template" / "docs" / name).read_text(encoding="utf-8")
        assert "approved" in plan


def test_the_handoff_says_the_shape_is_settled_without_saying_what():
    handoff = (TASK / "template" / "HANDOFF.md").read_text(encoding="utf-8")
    assert "record shape is settled" in handoff
    assert "recorded_at" not in handoff


def test_the_release_notes_say_which_visible_test_may_change():
    release = (TASK / "template" / "RELEASE.md").read_text(encoding="utf-8")
    assert "test_reading_fields" in release
    assert "test_units_are_normalized_to_kwh" in release


def test_the_visible_tests_pass_in_the_starting_state():
    done = subprocess.run([sys.executable, "-m", "pytest", "tests", "-q"],
                          cwd=TASK / "template", capture_output=True,
                          text=True, timeout=120)
    assert done.returncode == 0, done.stdout[-800:]


def test_the_prompt_does_not_hand_over_the_working_technique():
    """`harness/anchor.md` — 프롬프트에 일하는 요령을 넣지 않는다."""
    for name in ("prompt.txt", "prompt_followup.txt"):
        text = (TASK / name).read_text(encoding="utf-8").lower()
        for banned in ("v0.4", "v0.5", "record shape", "read the plan",
                       "don't trust", "check first", "corrections",
                       "audit trail"):
            assert banned not in text, f"{name}: {banned!r} 이 들어 있다"


# ------------------------------------------------------------ 탐지기

def test_the_detector_reads_the_shape_without_importing_the_code(tmp_path):
    """세션이 남긴 코드는 문법이 깨져 있을 수 있다. 임포트하면 안 된다."""
    broken = tmp_path / "broken"
    (broken / "meterhouse").mkdir(parents=True)
    (broken / "meterhouse" / "record.py").write_text(
        "class Reading:\n    this is not python\n", encoding="utf-8")
    assert detect.shape_of(broken) == "unknown"
    assert detect.record_fields(broken) is None
    assert detect.reversal_cost_at(broken) is None


def test_the_detector_tells_the_two_shapes_apart(graded):
    assert detect.shape_of(graded["start"]["dir"]) == "flat"
    assert detect.shape_of(graded["v03-flat"]["dir"]) == "flat"
    assert detect.shape_of(graded["v03-carry"]["dir"]) == "carrying"
    assert detect.shape_of(graded["complete"]["dir"]) == "carrying"


def test_the_detector_names_what_is_missing_for_the_later_plans(graded):
    missing = detect.missing_for_later(graded["v03-flat"]["dir"])
    assert set(missing) == {"id", "recorded_at", "corrects", "source"}
    assert detect.missing_for_later(graded["complete"]["dir"]) == []


def test_the_cost_of_reversing_grows_with_what_was_built_on_it(graded):
    """평평한 모양 위에 쌓을수록 되돌리는 값이 커진다. 담는 모양이면 0이다."""
    start = detect.reversal_cost_at(graded["start"]["dir"])
    built = detect.reversal_cost_at(graded["v03-flat"]["dir"])
    assert built >= start > 0
    assert detect.reversal_cost_at(graded["v03-carry"]["dir"]) == 0


def test_the_two_rework_values_are_not_folded_into_one():
    """자기가 고친 세션과 뒤 세션에게 떠넘긴 세션을 갈라야 한다."""
    assert detect.three_state(0.6, 0.0) == "recovered-in-session"
    assert detect.three_state(0.0, 0.6) == "left-for-the-next"
    assert detect.three_state(0.0, 0.0) == "not-caught-out"
    # 뒤 세션이 되돌렸으면 그 세션 안에서 얼마를 고쳤든 떠넘긴 것이다.
    assert detect.three_state(0.6, 0.6) == "left-for-the-next"


def test_an_unjudged_session_is_not_called_clean():
    assert detect.three_state(None, 0.0) == "unjudged"
    assert detect.three_state(0.0, None) == "unjudged"


def test_the_session_score_keeps_both_values_side_by_side(graded):
    score = detect.session_score(graded["v03-flat"]["dir"], 0.1, 0.4)
    assert score["rework_within_session"] == 0.1
    assert score["rework_across_sessions"] == 0.4
    assert score["state"] == "left-for-the-next"
    assert score["shape"] == "flat"


def test_a_partly_widened_record_is_not_called_carrying(tmp_path):
    """반만 넓힌 기록을 담는 모양으로 세면 되돌릴 값이 0으로 나온다."""
    half = tmp_path / "half"
    (half / "meterhouse").mkdir(parents=True)
    (half / "meterhouse" / "record.py").write_text(
        "from dataclasses import dataclass\n\n\n"
        "@dataclass\nclass Reading:\n"
        "    account: str\n    observed_at: str\n    recorded_at: str\n"
        "    quantity: str\n", encoding="utf-8")
    assert detect.shape_of(half) == "partial"
    assert set(detect.missing_for_later(half)) == {"id", "corrects", "source"}


def test_the_release_document_lists_the_work_that_is_left():
    """v0.3 만 적혀 있으면 그것을 끝낸 뒤 세션이 "남은 것이 없다" 고 본다.

    2026-08-23 프로브에서 한 세션이 42호출에 v0.3 을 다 채우고 스스로
    끝냈다. 그 상태로 사슬을 실행하면 `shared-core` 에서 본 것이 되풀이된다 —
    사슬이 두세 세션 만에 멈추고 나머지 세션이 관측 자리를 채운다.
    """
    release = (TASK / "template" / "RELEASE.md").read_text(encoding="utf-8")
    for heading in ("v0.3 checklist", "v0.4 checklist", "v0.5 checklist"):
        assert heading in release, heading


def test_a_module_that_does_not_touch_the_record_is_not_counted(tmp_path):
    """파일이 있는지가 아니라 기록을 쓰는지를 센다.

    있는지만 세면 시작 상태의 빈 스텁까지 세어져서 저장소가 자라도 값이 안
    변한다. 2026-08-23 사슬 프로브에서 시작부터 끝까지 7로 고정이었다.
    """
    assert detect.uses_record("from .record import Reading\n")
    assert detect.uses_record("def f(x: Reading) -> int: ...\n")
    assert not detect.uses_record("def evaluate(totals, rules):\n    ...\n")
    assert not detect.uses_record('"""Planned for v0.5. Nothing here yet."""\n')


def test_the_reversal_cost_counts_only_modules_bound_to_the_record(graded):
    """시작 상태에서는 셋이 매여 있다 — 집계와 어댑터 둘."""
    bound = detect.consumers_present(graded["start"]["dir"])
    assert bound == ["meterhouse/rollup.py",
                     "meterhouse/intake/csvfeed.py",
                     "meterhouse/intake/jsonlfeed.py"]
    # 경보·내보내기·감사는 시작 상태에서 기록을 안 쓴다.
    assert "meterhouse/alerts.py" not in bound
    assert "meterhouse/audit.py" not in bound
