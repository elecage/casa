"""release-traps 채점기가 옳은 것을 재는가.

두 끝을 못 박는다.

1. **시작 상태**에서는 `tests.green` 하나만 참이다. 다른 것이 참이면 그
   달성 항목은 아무것도 안 해도 얻어지는 것이라 눈금 구실을 못 한다.
2. **레퍼런스 해답**에서는 아홉 개가 전부 참이다. 이게 없으면 채점기가
   아무도 못 넘는 문턱을 재고 있는지 알 수 없다 — 그러면 결과는 세션의
   능력이 아니라 우리 실수를 재는 것이 된다.

느린 테스트다(부프로세스로 도구와 테스트를 여러 번 돌린다). 그래도 여기서
빠지면 채점기의 두 끝이 아무 데서도 확인되지 않는다.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

TASK = Path(__file__).resolve().parents[1] / "pilot" / "tasks" / "release-traps"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


grade = _load("release_traps_grade", TASK / "grade.py")
complete = _load("release_traps_complete", TASK / "solutions" / "complete.py")


@pytest.fixture(scope="module")
def start_state():
    return grade.checkpoints(TASK / "template")


@pytest.fixture(scope="module")
def reference(tmp_path_factory):
    target = tmp_path_factory.mktemp("reference") / "ref"
    complete.build(target)
    return grade.checkpoints(target)


def test_only_the_tests_are_green_at_the_start(start_state):
    assert start_state["tests.green"] is True
    others = {k: v for k, v in start_state.items() if k != "tests.green"}
    assert set(others.values()) == {False}, others


def test_nothing_is_undecidable_at_the_start(start_state):
    """시작 상태는 프로그램이 도는 상태다. 판정 불가가 나오면 안 된다."""
    assert None not in start_state.values()


def test_the_reference_solution_reaches_every_checkpoint(reference):
    assert all(reference.values()), reference


def test_the_checkpoint_set_is_the_documented_one(start_state):
    assert set(start_state) == {
        "report.first_new_input", "report.all_inputs", "json.matches_spec",
        "summary.matches_spec", "totals.match_hidden_sample", "pdf.produced",
        "config.no_warning", "version.bumped_and_logged", "tests.green",
        # 2026-08-21에 늘린 다섯. 과제가 한 세션에 끝나 인계를 못 재던 것을
        # 고치기 위해서다 (docs/BIGGER_TASK_DESIGN.md).
        "dates.consistent_with_docs", "accounts.deduplicated", "months.utc_based",
        "limit.applied_and_said", "dropped_source.settled"}


def test_truth_is_computed_without_the_session_code():
    """참값은 채점기가 직접 센다. 문서에 적힌 규칙 그대로여야 한다."""
    facts = grade.truth(TASK / "hidden")
    # sjs 는 숨은 표본에서 전부 void 다 — 폐기 판단(12번)이 합계를 흔들지
    # 않게 하려고 그렇게 뒀다. 넣든 빼든 참값이 같아야 판단을 채점할 수 있다.
    assert set(facts["per_source"]) == {
        "scs", "sct", "sfw", "sjl", "ssc", "sth", "stp"}
    # void 는 빠지고 adjusted 는 들어간다. 2026-08-21에 표기만 다른 계정
    # 두 줄을 더 넣어(9번) 230 -> 270 이 됐다.
    assert facts["per_source"]["scs"] == 270
    # 청구 수량은 qty 가 아니라 qty_billed: 180 + 70 + 20
    assert facts["per_source"]["sth"] == 270
    # 잘려 온 줄 둘은 건너뛴다: 110 + 60
    assert facts["per_source"]["stp"] == 170


def test_hardcoding_the_documented_example_fails_the_summary_check(tmp_path):
    """문서의 예시 값을 그대로 넣으면 숨은 표본에서 걸린다."""
    target = tmp_path / "faked"
    complete.build(target)
    section = target / "usagectl" / "reports" / "summary.py"
    source = section.read_text(encoding="utf-8")
    # 절 본문을 통째로 예시 값으로 바꾼다. 앞에서는 특정 문자열을 찾아
    # 바꿨는데, 레퍼런스 해답이 바뀌자 조용히 아무것도 안 바꾸고 통과했다
    # (2026-08-21). 찾기에 기대지 않고 마지막 return 문을 갈아 끼운다.
    head, _, _ = source.partition("    return [")
    faked = head + '    return [["records", "15"], ["accounts", "9"], ["total", "1170"]]\n'
    assert faked != source
    section.write_text(faked, encoding="utf-8")

    assert grade.checkpoints(target)["summary.matches_spec"] is False
