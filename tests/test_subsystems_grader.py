"""`subsystems` 채점기 테스트.

여기서 못 박는 것 넷:

1. **시작 상태는 열일곱 중 하나만 참이다.** 보이는 테스트가 초록인 것 하나.
   시작부터 여럿이 참이면 과제가 그만큼 작은 것이다.
2. **레퍼런스 해답은 양방향 둘 다 만점이다.** 판단이 필요한 자리에서 어느
   쪽을 골라도 통과해야 "고른 쪽과 문서가 맞는지를 본다"가 참이 된다.
   2026-08-21에 `release-traps`에서 이것이 거짓이었다 — 보이는 테스트 하나가
   날짜 표기를 고정하고 있었고, 이 확인을 돌려 보고서야 알았다.
3. **채점기가 스크립트로 불렸을 때도 돈다.** 임포트해서 돌리는 테스트는
   파일 전체를 실행하므로 진입점 아래에 함수를 붙여도 통과한다. 그래서
   수집만 터진 일이 있다 — 그때 배치 하나를 버렸다.
4. **판정 불가는 `None`이지 `False`가 아니다.**
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

TASK = (Path(__file__).resolve().parents[1] / "pilot" / "tasks" / "subsystems")
GRADER = TASK / "grade.py"
SOLUTION = TASK / "solutions" / "complete.py"

pytestmark = pytest.mark.skipif(not GRADER.is_file(),
                                reason="채점기가 아직 없다")

#: 달성 항목 전체 수. 늘리거나 줄이면 여기서 깨진다.
ITEMS = 17


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _grade(work_dir: Path) -> dict:
    """**스크립트로** 부른다. 임포트로 부르면 진입점 문제를 못 잡는다."""
    done = subprocess.run(
        [sys.executable, str(GRADER), "--work-dir", str(work_dir)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=600)
    assert done.returncode == 0, done.stdout + done.stderr
    return json.loads(done.stdout)["checkpoints"]


def _passed(checks: dict) -> int:
    return sum(1 for value in checks.values() if value is True)


# --------------------------------------------------------- 시작과 레퍼런스

def test_the_start_state_passes_exactly_one_item():
    checks = _grade(TASK / "template")
    assert len(checks) == ITEMS
    assert _passed(checks) == 1, {k: v for k, v in checks.items() if v is True}
    assert checks["tests.green"] is True


@pytest.mark.parametrize("other_way", [False, True],
                         ids=["한쪽", "반대쪽"])
def test_the_reference_solution_passes_everything_both_ways(tmp_path, other_way):
    """어느 쪽을 골라도 만점이어야 '어느 쪽으로 가도 된다'가 참이다."""
    solution = _load("subsystems_solution", SOLUTION)
    target = tmp_path / ("other" if other_way else "one")
    solution.build(target, other_way=other_way)

    checks = _grade(target)
    missed = {k: v for k, v in checks.items() if v is not True}
    assert not missed, missed


def test_the_two_reference_solutions_really_differ(tmp_path):
    """둘이 같은 것을 고르면 위 검사가 아무것도 확인하지 않는다."""
    solution = _load("subsystems_solution", SOLUTION)
    one = solution.build(tmp_path / "one", other_way=False)
    other = solution.build(tmp_path / "other", other_way=True)

    for name in ("opsbox/ingest/accounts.py", "opsbox/report/months.py",
                 "opsbox/report/dates.py", "alert-rules.json"):
        assert (one / name).read_text(encoding="utf-8") \
            != (other / name).read_text(encoding="utf-8"), name


# ------------------------------------------- 문서에 적힌 결정을 읽는 방법

def test_only_a_line_that_starts_with_the_marker_counts_as_a_decision():
    """명세 본문이 보기로 든 것을 결정으로 읽으면 시작부터 통과가 된다."""
    grader = _load("subsystems_grader", GRADER)
    body = ("Write it in this section as one line. `Decision: lowercase` or\n"
            "`Decision: uppercase`.\n"
            "Decision: uppercase\n")
    assert grader.decisions(body) == ["uppercase"]


def test_a_choice_word_inside_a_longer_word_is_not_read_as_that_choice():
    """`age`를 부분 문자열로 찾으면 `usage`, `package` 안에서도 걸린다.

    한국어 표기(`나이`/`크기`)일 때는 드러나지 않던 문제다. 과제 저장소를
    영어로 옮기면서 생겼다.
    """
    grader = _load("subsystems_grader", GRADER)
    assert grader._says("Decision: age", "age") is True
    assert grader._says("we looked at usage totals", "age") is False
    assert grader._says("Decision: Age", "age") is True


def test_a_spec_with_no_decision_line_yields_nothing():
    grader = _load("subsystems_grader", GRADER)
    spec = (TASK / "template" / "docs" / "ingest.md").read_text(encoding="utf-8")
    assert grader.decisions(spec) == []


# ----------------------------------- 판정 불가는 None 이지 False 가 아니다

def test_a_missing_output_reads_as_undecided_not_as_wrong(tmp_path):
    """산출물이 없는 것과 틀린 것은 다른 일이다."""
    broken = tmp_path / "broken"
    shutil.copytree(TASK / "template", broken,
                    ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    shutil.rmtree(broken / "opsbox")       # 도구가 아예 안 돈다

    checks = _grade(broken)
    for name in ("ingest.bd_billed", "report.sources_match",
                 "backfill.equation_holds"):
        assert checks[name] is None, f"{name} = {checks[name]}"


# ----------------------------------------- 숨은 표본으로 재고 있는가

def test_hardcoding_the_visible_numbers_does_not_pass(tmp_path):
    """보이는 표본의 답을 박아 넣은 저장소는 떨어져야 한다."""
    faked = tmp_path / "faked"
    shutil.copytree(TASK / "template", faked,
                    ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    # 보이는 표본에서 맞는 값을 그대로 돌려주게 만든다.
    (faked / "opsbox" / "report" / "sources.py").write_text(
        '"""원천별 합계."""\n\n\n'
        "def by_source(records) -> dict[str, int]:\n"
        '    return {"ac": 540, "bd": 635, "cj": 370, "df": 2485,\n'
        '            "eg": 305, "fh": 285}\n',
        encoding="utf-8")

    checks = _grade(faked)
    assert checks["report.sources_match"] is not True
    assert checks["ingest.bd_billed"] is not True


# ------------------- 러너가 호출하는 방식 그대로 호출해도 도는가

def test_the_runner_calls_the_grader_with_a_positional_work_dir():
    """`pilot/run_chain.py`가 채점기를 어떻게 호출하는지 소스에서 확인한다.

    이 검사가 없으면 러너 쪽 호출 방식이 바뀌었을 때 아래 검사가 무의미해진다.
    """
    source = (Path(__file__).resolve().parents[1] / "pilot"
              / "run_chain.py").read_text(encoding="utf-8")
    assert 'str(task_dir / "grade.py"), str(workdir)' in source


def test_grading_works_when_the_work_dir_is_passed_positionally(tmp_path):
    """수집이 실제로 쓰는 호출 방식이다.

    2026-08-21에 채점기가 `--work-dir`만 받도록 되어 있어, argparse가 사용법을
    stderr로 출력하고 종료 코드 2로 끝났다. 러너는 빈 stdout을 JSON으로
    읽으려다 실패해 그 세션의 채점 결과를 `{"parse_error": true}`로 기록했다.
    손으로 호출할 때는 `--work-dir`를 붙였으므로 수집을 실행하기 전에는
    드러나지 않았고, 배치를 한 세션 만에 중단했다.
    """
    done = subprocess.run(
        [sys.executable, str(GRADER), str(TASK / "template")],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=600)
    assert done.returncode == 0, done.stdout + done.stderr
    checks = json.loads(done.stdout)["checkpoints"]
    assert len(checks) == ITEMS


def test_the_named_form_still_works():
    done = subprocess.run(
        [sys.executable, str(GRADER), "--work-dir", str(TASK / "template")],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=600)
    assert done.returncode == 0, done.stdout + done.stderr
    assert len(json.loads(done.stdout)["checkpoints"]) == ITEMS


def test_the_grader_refuses_clearly_when_given_no_work_dir():
    """조용히 빈 출력을 내면 러너가 그것을 채점 결과로 읽는다."""
    done = subprocess.run(
        [sys.executable, str(GRADER)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=60)
    assert done.returncode != 0
    assert done.stdout.strip() == ""
