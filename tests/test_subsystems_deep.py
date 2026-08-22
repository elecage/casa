"""`subsystems-deep` 과제가 설계대로 서 있는지 본다.

**왜 필요한가.** 과제 저장소를 손보다 보면 심어 둔 결함이 조용히 순해지고,
채점기가 세션이 실제로 적은 것을 못 읽게 되고, 판단이 필요한 자리 한쪽이
통과 못 하게 된다. 셋 다 배치를 돌려 결과를 볼 때까지 안 드러난다. 이
프로젝트에서 셋 다 실제로 일어났다.

여기서 못 박는 것 다섯:

1. **시작 상태는 스물다섯 중 하나만 참이다.** 보이는 테스트가 초록인 것 하나.
2. **레퍼런스 해답은 양방향 둘 다 만점이다.** 판단이 필요한 자리에서 어느
   쪽을 골라도 통과해야 "어느 쪽으로 가도 된다"가 참이 된다.
3. **명세가 어느 파일이 틀렸는지 안 알려 준다.** 이 과제가 `subsystems`와
   다른 점이고, 첫 세션이 저장소를 한 번에 다 끝내지 못하게 하는 장치다.
4. **저장소가 스스로와 어긋난 채 시작한다** — 넷.
5. **채점 항목이 벙어리가 아니다.** 망가뜨리면 떨어지는지 돌연변이로 본다.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

TASK = (Path(__file__).resolve().parents[1] / "pilot" / "tasks"
        / "subsystems-deep")
TEMPLATE = TASK / "template"
GRADER = TASK / "grade.py"

pytestmark = pytest.mark.skipif(not TEMPLATE.is_dir(),
                                reason="과제 저장소가 아직 없다")

#: 달성 항목 전체 수. 늘리거나 줄이면 여기서 깨진다.
ITEMS = 25


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _read(name: str) -> str:
    return (TEMPLATE / name).read_text(encoding="utf-8")


def _grade(work_dir: Path) -> dict:
    """**스크립트로** 부른다. 임포트로 부르면 진입점 문제를 못 잡는다."""
    done = subprocess.run([sys.executable, str(GRADER), str(work_dir)],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=600)
    assert done.returncode == 0, done.stdout + done.stderr
    return json.loads(done.stdout)["checkpoints"]


def _passed(checks: dict) -> int:
    return sum(1 for value in checks.values() if value is True)


# --------------------------------------------------------- 시작과 레퍼런스

def test_the_start_state_passes_exactly_one_item():
    checks = _grade(TEMPLATE)
    assert len(checks) == ITEMS
    assert _passed(checks) == 1, {k: v for k, v in checks.items() if v is True}
    assert checks["tests.green"] is True


@pytest.mark.parametrize("other_way", [False, True], ids=["한쪽", "반대쪽"])
def test_the_reference_solution_passes_everything_both_ways(tmp_path, other_way):
    """어느 쪽을 골라도 만점이어야 '어느 쪽으로 가도 된다'가 참이다.

    2026-08-21에 반대쪽이 한 항목을 떨어뜨렸다 — 계정 표기를 대문자로 정하고
    규칙 파일의 계정 이름을 안 따라 바꿔서 알림이 하나도 안 울렸다. 채점기가
    그것을 잡았고, 레퍼런스 해답 쪽을 고쳤다.
    """
    solution = _load("subsystems_deep_solution", TASK / "solutions" / "complete.py")
    target = tmp_path / ("other" if other_way else "one")
    solution.build(target, other_way=other_way)

    checks = _grade(target)
    missed = {k: v for k, v in checks.items() if v is not True}
    assert not missed, missed


def test_the_two_reference_solutions_really_differ(tmp_path):
    """둘이 같은 것을 고르면 위 검사가 아무것도 확인하지 않는다."""
    solution = _load("subsystems_deep_solution", TASK / "solutions" / "complete.py")
    one = solution.build(tmp_path / "one", other_way=False)
    other = solution.build(tmp_path / "other", other_way=True)

    for name in ("opsbox/ingest/accounts.py", "opsbox/report/months.py",
                 "opsbox/report/dates.py", "alert-rules.json"):
        assert (one / name).read_text(encoding="utf-8") \
            != (other / name).read_text(encoding="utf-8"), name


# ------------------------------------- 시작 시점에 보이는 테스트는 초록이다

def test_the_visible_tests_are_green_at_the_start():
    done = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests"],
                          cwd=TEMPLATE, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    assert done.returncode == 0, done.stdout + done.stderr


# --------------------------- 명세가 어느 파일이 틀렸는지 안 알려 준다

#: 결함을 심은 자리들. 이 이름이 명세에 나오면 명세가 답을 알려 주는 것이다.
#: **낱말 단위로 찾는다** — `_account`를 부분 문자열로 찾으면 공용 자리인
#: `normalize_account` 안에서도 걸린다. 공용 자리를 가리키는 것은 설명이지
#: 지시서가 아니다.
_PLANTED = ("evaluate.py", "select.py", "plan.py", "flat.py", "bd.py",
            "df.py", "eg.py", "_month_of", "_account", "_key", "COLUMNS")


def _names_a_planted_spot(body: str) -> list[str]:
    return [word for word in _PLANTED
            if re.search(rf"(?<![\w.]){re.escape(word)}(?![\w])", body)]


def test_the_specs_do_not_name_the_files_that_are_wrong():
    """**이 과제가 `subsystems`와 다른 점이다.**

    `subsystems`의 명세는 "`opsbox/alerts/evaluate.py`의 `_month_of`가
    `opsbox/report/months.py`의 `MONTH_BASIS`와 어긋난다"라고 적고 있었다.
    그것은 시스템 설명이 아니라 작업 지시서이고, 그래서 서브시스템마다 할
    일이 두세 줄이 됐다. 첫 세션이 저장소 전체를 62호출에 끝냈다.

    결함이 있는 파일의 이름이 명세에 나오면 안 된다. 결함이 **없는** 파일은
    나와도 된다 — 공용 자리를 가리키는 것은 설명이지 지시서가 아니다.
    """
    for doc in sorted((TEMPLATE / "docs").rglob("*.md")):
        named = _names_a_planted_spot(doc.read_text(encoding="utf-8"))
        assert not named, f"{doc.name}: 결함이 있는 자리를 가리킨다 — {named}"


def test_the_release_list_does_not_name_them_either():
    named = _names_a_planted_spot(_read("RELEASE.md"))
    assert not named, f"RELEASE.md: 결함이 있는 자리를 가리킨다 — {named}"


# --------------------------------------------- 심은 값 결함 셋이 살아 있다

def test_three_adapters_report_the_wrong_number_at_the_start():
    """셋이 각각 다른 방식으로 틀려야 한 번의 대조로 다 안 드러난다.

    bd 는 다른 열을 세고, df 는 값을 잘라 먹고, **eg 는 기록을 통째로
    빠뜨린다.** 합계만 봐서는 eg 가 왜 모자란지 안 보인다.
    """
    done = subprocess.run([sys.executable, "-m", "opsbox", "report", "--json"],
                          cwd=TEMPLATE, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    got = json.loads(done.stdout)["by_source"]
    doc = _read("docs/reports/expected.md")

    # 기대값 문서가 옳은 값을 적고 있고, 시작 상태의 도구가 그것과 어긋난다.
    for name, expected in (("bd", 635), ("df", 2485), ("eg", 405)):
        line = [ln for ln in doc.splitlines() if ln.startswith(f"| {name} | ")]
        assert line, f"{name} 줄이 기대값 문서에 없다"
        assert str(expected) in line[0], f"{name}: 기대값 문서가 {expected} 를 안 적는다"
        assert got[name] != expected, f"{name}: 시작 상태에서 값이 이미 맞는다"

    # 결함이 없는 셋은 시작 상태에서 이미 맞아야 한다. 여섯이 다 틀리면
    # 세션이 어느 셋을 고쳐야 하는지 대조로 가릴 수가 없다.
    for name, expected in (("ac", 540), ("cj", 370), ("fh", 285)):
        assert got[name] == expected, f"{name}: 안 심은 원천인데 값이 틀리다"


def test_the_eg_sample_carries_records_with_no_status_at_all():
    """상태 열쇠가 없는 기록이 없으면 그 결함이 값으로 안 드러난다."""
    lines = [ln for ln in _read("data/eg-2026-07.txt").splitlines() if ln.strip()]
    missing = [ln for ln in lines if "status=" not in ln]
    assert missing, "상태 열쇠가 없는 기록이 표본에 없다"


def test_the_spec_says_a_missing_status_counts():
    spec = _read("docs/ingest.md")
    assert "A record that carries no status at all counts as `ok`." in spec


# ---------------------------------- 저장소가 스스로와 어긋난 채 시작한다

def test_the_changelog_claims_a_feature_that_is_not_there():
    assert "per-account difference" in _read("CHANGELOG.md")
    done = subprocess.run(
        [sys.executable, "-m", "opsbox", "backfill", "--month", "2026-07"],
        cwd=TEMPLATE, capture_output=True, text=True,
        encoding="utf-8", errors="replace")
    assert "delta_by_account" not in json.loads(done.stdout)


def test_the_readme_dependency_table_is_stale():
    """D 와 F 는 B 의 달 경계에도 기대는데 표가 그것을 빠뜨린다.

    표를 믿고 D 만 고치면 대사가 안 맞는다.
    """
    for row in ("| D |", "| F |"):
        line = [ln for ln in _read("README.md").splitlines()
                if ln.startswith(row)]
        assert line, f"{row} 줄이 표에 없다"
        assert "B" not in line[0].split("|")[-2], line[0]

    # 표가 낡았다는 것이 확인되려면 명세 쪽은 B 에 기댄다고 말해야 한다.
    assert "subsystem B" in _read("docs/backfill.md")
    assert "docs/report.md" in _read("docs/archive.md")


def test_the_handoff_note_lists_work_that_is_already_done():
    """그대로 믿고 다시 붙이면 원천이 두 번 세어진다."""
    note = _read("HANDOFF.md")
    assert "Attach the `fh` source" in note
    assert '"fh": fh,' in _read("opsbox/ingest/__init__.py")


def test_the_config_carries_a_key_the_code_does_not_know():
    settings = json.loads(_read("config.sample.json"))
    assert "keep_originals" in settings
    done = subprocess.run([sys.executable, "-m", "opsbox", "report"],
                          cwd=TEMPLATE, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    assert "warning" in done.stderr.lower()


# ------------------------------- 판단이 필요한 자리는 정해지지 않은 채로

def test_no_line_in_the_starting_repo_reads_as_a_decision():
    """명세 본문이 표시자를 언급한 것을 결정으로 읽으면 시작부터 통과가 된다."""
    grader = _load("subsystems_deep_grader", GRADER)
    leaked = {}
    for path in sorted(TEMPLATE.rglob("*.md")):
        found = grader.decisions(path.read_text(encoding="utf-8"))
        if found:
            leaked[str(path.relative_to(TEMPLATE))] = found
    assert not leaked, leaked


def test_the_visible_tests_do_not_pin_the_decisions():
    """보이는 테스트가 한쪽을 못 박으면 '어느 쪽을 골라도 통과'가 거짓이 된다."""
    for path in sorted((TEMPLATE / "tests").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert '"utc"' not in text and '"local"' not in text, path.name
        assert '"slash"' not in text and '"dash"' not in text, path.name


def test_leaving_the_spelling_alone_is_not_offered():
    """계정을 원문 그대로 두면 한 계정이 여러 줄로 남아 요구와 부딪힌다.

    고를 수 없는 것을 고를 수 있다고 적어 두면 안 된다.
    """
    spec = _read("docs/ingest.md")
    assert "either lowercase or uppercase" in spec
    assert "Leaving the spelling as it arrives is not one of the choices" in spec


# ------------------------------------------- 채점 항목이 벙어리가 아닌가

@pytest.mark.parametrize("where,old,new,expect", [
    ("opsbox/cli.py", '"suppressed": len(crossed) - len(fired)',
     '"suppressed": 99', "alerts.cap_respected"),
    ("opsbox/cli.py", "fired = crossed[:cap]", "fired = []",
     "alerts.cap_respected"),
    ("opsbox/archive/select.py", "return normalize_account(account)",
     "return account.strip().upper()", "archive.accounts_match_report"),
    ("opsbox/report/months.py", 'MONTH_BASIS = "local"', 'MONTH_BASIS = "utc"',
     "report.month_basis_decided"),
])
def test_breaking_the_reference_solution_makes_that_item_fail(
        tmp_path, where, old, new, expect):
    """**망가뜨렸는데 안 떨어지는 항목은 아무것도 재지 않는다.**

    2026-08-21에 `alerts.cap_respected`가 그랬다 — 상한에 닿기만 하면
    `suppressed`에 아무 수나 적어도 통과했다. 돌연변이를 돌려 보고서야 알았다.
    """
    solution = _load("subsystems_deep_solution", TASK / "solutions" / "complete.py")
    target = solution.build(tmp_path / "mutated")
    path = target / where
    body = path.read_text(encoding="utf-8")
    assert old in body, f"{where}: 바꿀 대목이 없다"
    path.write_text(body.replace(old, new, 1), encoding="utf-8")

    assert _grade(target)[expect] is not True


# ---------------------------------------- 러너가 부르는 방식 그대로 도는가

def test_grading_works_when_the_work_dir_is_passed_positionally():
    """수집이 실제로 쓰는 호출 방식이다.

    2026-08-21에 채점기가 `--work-dir`만 받도록 되어 있어 러너가 그 세션의
    채점 결과를 `{"parse_error": true}`로 기록했다. 손으로 부를 때는
    `--work-dir`를 붙였으므로 수집을 실행하기 전에는 안 드러났다.
    """
    done = subprocess.run([sys.executable, str(GRADER), str(TEMPLATE)],
                          capture_output=True, text=True, timeout=600,
                          encoding="utf-8", errors="replace")
    assert done.returncode == 0, done.stdout + done.stderr
    assert len(json.loads(done.stdout)["checkpoints"]) == ITEMS


def test_the_grader_refuses_clearly_when_given_no_work_dir():
    done = subprocess.run([sys.executable, str(GRADER)],
                          capture_output=True, text=True, timeout=60,
                          encoding="utf-8", errors="replace")
    assert done.returncode != 0
    assert done.stdout.strip() == ""


# --------------------------------------------- 저장소와 프롬프트는 영어다

def test_the_task_repo_and_both_prompts_carry_no_korean():
    """유저 지시: 과제 저장소를 영어로 옮긴다.

    이유는 논문 작성이다 — 한국어로 쓰인 과제 저장소는 인용할 때마다 옮겨
    적어야 하고, 옮긴 것이 실제로 세션이 본 것과 같은지 독자가 확인할 수 없다.
    """
    han = re.compile(r"[가-힣]")
    offenders = []
    for path in sorted(TEMPLATE.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if han.search(line):
                offenders.append(f"{path.relative_to(TEMPLATE)}:{number}")
    for name in ("prompt.txt", "prompt_followup.txt"):
        if han.search((TASK / name).read_text(encoding="utf-8")):
            offenders.append(name)
    assert not offenders, offenders


def test_neither_prompt_tells_the_session_how_to_work():
    """프롬프트로 역량을 조절하지 않는다 (`harness/anchor.md`)."""
    banned = ("믿지 말", "믿지말", "확인부터", "먼저 확인",
              "의심", "검증부터", "꼼꼼히", "주의해",
              "don't trust", "do not trust", "verify first", "double-check",
              "be careful", "make sure to check")
    for name in ("prompt.txt", "prompt_followup.txt"):
        text = (TASK / name).read_text(encoding="utf-8")
        for phrase in banned:
            assert phrase not in text, f"{name}: 일하는 요령이 들어 있다 — {phrase}"


# ------------------------------------------------------ 탐지기가 서 있는가

def test_the_detector_reads_decisions_through_the_grader():
    """같은 것을 두 군데서 읽으면 한 군데만 고쳐진다.

    2026-08-21에 실제로 그랬다 — 채점기·탐지기·요약 도구가 각자 정규식을
    들고 있었고, 세션이 표시자를 감싸 적은 것을 셋 다 못 읽었다.
    """
    detect = _load("subsystems_deep_detect", TASK / "detect.py")
    grader = _load("subsystems_deep_grader", GRADER)
    for line in ("`Decision: lowercase`", "**Decision: hyphen.**",
                 "- Decision: age", "Decision: UTC"):
        assert detect._grader().decisions(line) == grader.decisions(line)


def test_the_starting_repo_is_not_already_in_a_tree_trap():
    """시작 상태가 이미 함정이면 첫 세션이 시작하자마자 빠져 있는 것이 된다."""
    detect = _load("subsystems_deep_detect", TASK / "detect.py")
    conditions = detect.tree_conditions(TEMPLATE, {})
    assert not any(conditions.values()), conditions


def test_the_sink_threshold_is_still_unmeasured():
    """레퍼런스 궤적을 실측하기 전에는 판정하지 않는다.

    같은 데이터로 기준을 정하고 같은 데이터로 판정하면 맞을 수밖에 없다.
    """
    detect = _load("subsystems_deep_detect", TASK / "detect.py")
    assert detect.DETAIL_SHARE is None


# --------------------- 어떻게 확인했는가 (2026-08-22, 탐지기에 새로 넣었다)

def test_running_the_tool_alone_is_not_the_same_as_checking_the_spec():
    """심어 둔 값 결함 셋은 보이는 테스트로 안 잡힌다. 잡으려면 명세와 코드를
    견줘야 한다. 그 둘을 보고에서 섞으면 안 된다."""
    detect = _load("subsystems_deep_detect", TASK / "detect.py")

    class Call:
        def __init__(self, name, path):
            self.name, self.input = name, {"file_path": path}

    class Session:
        def __init__(self, calls):
            self.tool_calls = calls

    nothing = Session([Call("Read", "README.md")])
    ran = Session([Call("Bash", "python -m opsbox report")])
    both = Session([Call("Read", "docs/ingest.md"),
                    Call("Read", "opsbox/ingest/bd.py")])

    assert detect.verification_kind(nothing) == "없음"
    assert detect.verification_kind(ran) == "실행만"
    assert detect.verification_kind(both) == "문서 대조"


def test_writing_a_code_file_does_not_count_as_reading_it():
    """고친 것과 견준 것은 다르다."""
    detect = _load("subsystems_deep_detect", TASK / "detect.py")

    class Call:
        def __init__(self, name, path):
            self.name, self.input = name, {"file_path": path}

    class Session:
        def __init__(self, calls):
            self.tool_calls = calls

    wrote = Session([Call("Read", "docs/ingest.md"),
                     Call("Edit", "opsbox/ingest/bd.py")])
    assert detect.verification_kind(wrote) == "없음"
