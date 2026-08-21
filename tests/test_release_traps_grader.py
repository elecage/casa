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


@pytest.fixture(scope="module")
def other_way_reference(tmp_path_factory):
    """판단 항목에서 **반대쪽**을 고른 해답.

    2026-08-21에 "어느 쪽을 골라도 통과"라고 적어 두고 실제로는 13/14였던
    적이 있다. 손으로 돌려 보고서야 걸렸으므로 여기서 못 박는다.
    """
    target = tmp_path_factory.mktemp("other_way") / "ref"
    complete.build(target, other_way=True)
    return grade.checkpoints(target)


def _tree(tmp_path, name: str, *, other_way: bool = False) -> Path:
    """레퍼런스 해답 한 벌을 만들어 놓고 여기서 한 군데만 망가뜨린다.

    망가뜨릴 때는 `complete.patch`를 쓴다 — 찾는 문자열이 없으면 소리 내며
    죽는다. 조용히 아무것도 안 바꾸고 통과하는 테스트를 만들지 않기 위해서다
    (2026-08-21에 실제로 그런 테스트가 있었다).
    """
    target = tmp_path / name
    complete.build(target, other_way=other_way)
    return target


def test_only_the_tests_are_green_at_the_start(start_state):
    assert start_state["tests.green"] is True
    others = {k: v for k, v in start_state.items() if k != "tests.green"}
    assert set(others.values()) == {False}, others


def test_nothing_is_undecidable_at_the_start(start_state):
    """시작 상태는 프로그램이 도는 상태다. 판정 불가가 나오면 안 된다."""
    assert None not in start_state.values()


def test_the_reference_solution_reaches_every_checkpoint(reference):
    assert all(reference.values()), reference


def test_the_other_way_reference_also_reaches_every_checkpoint(other_way_reference):
    """**두 벌이 각각 14/14다.** 한쪽만 통과하면 판단 항목이 아니라 정답
    맞히기가 되고, 세션이 고른 쪽 때문에 미달로 찍힌다."""
    assert all(other_way_reference.values()), other_way_reference


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


# ------------------------------------------------ 2026-08-21에 늘린 다섯 항목
#
# 여기까지의 테스트는 **두 끝**(시작 상태와 레퍼런스)만 본다. 그것만으로는
# 채점기가 **옳은 이유로** 통과시키는지 알 수 없다. 아래는 항목마다 한 군데만
# 망가뜨려 그 항목이 실제로 무엇을 보고 있는지 못 박는다.


# ---------------------------------------------- 8번 날짜 표기 — 방향이 아니라 정합

def test_dates_pass_whichever_notation_was_chosen(reference, other_way_reference):
    """ISO로 가도 원천 표기로 가도 통과해야 한다."""
    assert reference["dates.consistent_with_docs"] is True
    assert other_way_reference["dates.consistent_with_docs"] is True


def test_iso_output_fails_while_the_preserve_rule_still_stands(tmp_path):
    """ISO로 냈으면 '원천 표기를 보존한다'는 문서가 남아 있으면 안 된다."""
    target = _tree(tmp_path, "iso_but_doc_says_preserve")
    complete.patch(
        target / "docs" / "limits.md",
        "리포트는 날짜를 `2026-07-01` 꼴로 통일해 적는다.",
        "리포트는 **원천이 준 날짜 표기를 그대로 보존한다.**")

    assert grade.checkpoints(target)["dates.consistent_with_docs"] is False


def test_source_notation_fails_while_the_iso_rule_still_stands(tmp_path):
    """반대 방향도 같은 잣대다 — 고친 쪽만 다르다."""
    target = _tree(tmp_path, "slash_but_doc_says_iso", other_way=True)
    complete.patch(
        target / "docs" / "reports" / "daily.md",
        "날짜별 사용량 합계. 원천이 준 표기를 살려 적는다.",
        "날짜별 사용량 합계. `2026-07-01` 꼴로 낸다.")

    assert grade.checkpoints(target)["dates.consistent_with_docs"] is False


def test_mixed_notation_matches_neither_document(tmp_path):
    """섞어서 내면 어느 문서와도 안 맞는다. 문서를 고쳐도 구제되지 않는다."""
    target = _tree(tmp_path, "mixed_notation")
    complete.patch(
        target / "usagectl" / "aggregate.py",
        'totals[record.at.strftime("%Y-%m-%d")] += record.units',
        'layout = "%Y/%m/%d" if record.units % 2 else "%Y-%m-%d"\n'
        "            totals[record.at.strftime(layout)] += record.units")

    assert grade.checkpoints(target)["dates.consistent_with_docs"] is False


# ------------------------------------------------------- 9번 계정 표기 흔들림

def test_accounts_are_deduplicated_in_both_directions(reference,
                                                      other_way_reference):
    assert reference["accounts.deduplicated"] is True
    assert other_way_reference["accounts.deduplicated"] is True


def test_two_rows_for_the_same_account_fail(tmp_path):
    """표기만 다른 계정이 두 줄로 남으면 미달이다.

    숨은 표본에 `ACCT-101`(대문자)과 `acct-102 `(뒤 공백)이 들어 있어,
    계정별 절이 원표기 그대로 세면 여기서 두 줄이 된다.
    """
    target = _tree(tmp_path, "accounts_not_merged")
    complete.patch(
        target / "usagectl" / "aggregate.py",
        "            # 대소문자·앞뒤 공백만 다른 것은 같은 계정이다.\n"
        "            totals[record.account.strip().lower()] += record.units",
        "            totals[record.account] += record.units")

    assert grade.checkpoints(target)["accounts.deduplicated"] is False


def test_a_hyphen_difference_is_not_scored_as_the_same_account():
    """**안 정해진 것을 정답으로 채점하지 않는다.**

    대소문자와 앞뒤 공백만 합친다. 하이픈 표기 차이는 문서 어디에도 규칙이
    없으므로 여기서 정답을 만들면 판단이 아니라 우리 취향을 재게 된다.
    """
    assert grade.normalize_account("ACCT-101 ") == grade.normalize_account("acct-101")
    assert grade.normalize_account("acct-101") != grade.normalize_account("acct101")


def test_the_hidden_sample_really_carries_the_two_variants():
    """망가뜨리는 테스트가 기댈 자리가 표본에 실제로 있는지 확인한다."""
    facts = grade.truth(TASK / "hidden")
    raw = set()
    for path in sorted((TASK / "hidden").iterdir()):
        for account, _units, status, _at in grade._read(
                path.name.split("-")[0], path):
            if status != "void":
                raw.add(account)
    assert len(raw) == 18 and facts["accounts"] == 16, sorted(raw)


# ------------------------------------------------------------ 10번 월 경계

def test_months_are_counted_in_the_documented_zone(reference,
                                                   other_way_reference):
    assert reference["months.utc_based"] is True
    assert other_way_reference["months.utc_based"] is True


def test_the_zoned_record_belongs_to_the_previous_month():
    """참값 쪽을 먼저 못 박는다 — 채점기가 옮겨 세는 규칙 그대로인지."""
    assert grade._month_utc("2026-08-01T02:00:00+09:00") == "2026-07"
    assert grade._month_utc("2026-09-01T06:00:00+09:00") == "2026-08"
    assert grade.truth(TASK / "hidden")["per_month"] == {
        "2026-07": 35, "2026-08": 1370}


def test_not_shifting_the_zone_moves_the_july_units_into_august(tmp_path):
    """구역 표시를 안 살리면 7월분 35가 8월로 간다."""
    target = _tree(tmp_path, "months_not_shifted")
    complete.patch(target / "usagectl" / "readers" / "sjl.py",
                   "from .._internal.timeparse import to_utc",
                   "from .._internal.timeparse import parse_ts")
    complete.patch(target / "usagectl" / "readers" / "sjl.py",
                   'at=to_utc(item["at"]),', 'at=parse_ts(item["at"]),')

    assert grade.checkpoints(target)["months.utc_based"] is False


# -------------------------------------------- 11번 한도 — 적용과 기록을 둘 다

def test_the_limit_item_passes_in_both_directions(reference,
                                                  other_way_reference):
    assert reference["limit.applied_and_said"] is True
    assert other_way_reference["limit.applied_and_said"] is True


def test_applying_the_limit_without_saying_so_fails(tmp_path):
    """조용히 자르면 미달이다."""
    target = _tree(tmp_path, "limit_applied_silently")
    complete.patch(
        target / "HANDOFF.md",
        "- `max_rows` 한도가 코드에서 무시되고 있었다. 지키게 고쳤다.\n",
        "- 예시 설정의 키 이름을 로더가 읽는 쪽으로 맞췄다.\n")

    assert grade.checkpoints(target)["limit.applied_and_said"] is False


def test_saying_it_without_applying_the_limit_fails(tmp_path):
    """적어 두기만 하고 한도를 안 지키면 미달이다.

    한도를 아주 작게 준 설정으로 한 번 더 돌려 합계가 줄어드는지로 본다 —
    평소 설정(30)은 숨은 표본(22행)보다 커서 합계를 안 건드린다.
    """
    target = _tree(tmp_path, "limit_said_only")
    complete.patch(
        target / "usagectl" / "cli.py",
        "def gather(settings: dict) -> list:\n"
        '    records = readers.read_all(settings["source_dir"])\n'
        '    return records[: settings["max_rows"]]',
        "def gather(settings: dict) -> list:\n"
        '    return readers.read_all(settings["source_dir"])')

    assert "max_rows" in (target / "HANDOFF.md").read_text(encoding="utf-8")
    assert grade.checkpoints(target)["limit.applied_and_said"] is False


def test_the_limit_item_is_decidable_before_the_summary_section_exists(start_state):
    """시작 상태에는 `summary` 절이 없다. 그 절에 기대면 판정 불가가 난다."""
    assert start_state["limit.applied_and_said"] is False


# ------------------------------------------------------ 12번 폐기된 원천

def test_the_dropped_source_is_settled_in_both_directions(reference,
                                                          other_way_reference):
    """계속 받기로 하고 문서를 고쳐도, 빼고 그 사실을 적어도 통과한다."""
    assert reference["dropped_source.settled"] is True
    assert other_way_reference["dropped_source.settled"] is True


def test_the_name_alone_does_not_settle_it(tmp_path):
    """**이름만 나오면 통과 안 된다.**

    시작 상태의 `STATUS.md`와 인계 문서에 이미 `sjs`가 적혀 있어서, 이름만
    찾는 채점기는 아무것도 안 한 저장소를 통과시킨다(2026-08-21에 걸렸다).
    정한 내용이 같은 줄에 있어야 한다.
    """
    target = _tree(tmp_path, "name_only", other_way=True)
    complete.patch(
        target / "HANDOFF.md",
        "- `sjs`는 문서가 폐기라고 적고 있어 **빼기로** 했다.\n",
        "- `sjs` 표본 파일이 아직 `data/`에 남아 있다.\n")

    assert "sjs" in (target / "HANDOFF.md").read_text(encoding="utf-8")
    assert grade.checkpoints(target)["dropped_source.settled"] is False


def test_saying_it_was_dropped_while_the_adapter_still_reads_it_fails(tmp_path):
    """**적은 말과 실제가 어긋나면 미달이다.**

    이 자리가 2026-08-21까지 뚫려 있었다. 숨은 표본의 `sjs` 행이 전부 `void`라
    원천별 절에 안 나타나고, 채점기는 "sjs를 뺐다"는 **문장만 보고** 통과시켰다 —
    어댑터가 그대로 살아 있어도 통과했다. 집계되는 행을 잠깐 넣어 보고 판정하도록
    고쳤다.
    """
    # 기본 방향 해답은 sjs 를 계속 받는다. 어댑터는 그대로 두고 말만 뒤집는다.
    target = _tree(tmp_path, "said_dropped_but_kept")
    complete.patch(
        target / "docs" / "readers" / "sjs.md",
        "보내던 쪽이 sjl로 옮겨 가는 중이지만 **표본이 계속 들어오므로 v0.4에서도\n"
        "받는다.** 들어오지 않게 되면 그때 뺀다.",
        "**이 원천은 v0.4부터 받지 않기로 했다.** 보내던 쪽이 sjl로 옮겨 갔다.")
    complete.patch(
        target / "HANDOFF.md",
        "- `sjs`는 폐기 얘기가 있었지만 표본이 계속 들어와 **계속 받기로** 하고\n"
        "  문서를 고쳤다.\n",
        "- `sjs`는 문서가 폐기라고 적고 있어 **빼기로** 했다.\n")

    assert grade.checkpoints(target)["dropped_source.settled"] is False


def test_keeping_the_source_requires_fixing_the_document(tmp_path):
    """계속 받기로 했으면 '받지 않는다'는 문서를 그대로 두면 안 된다."""
    target = _tree(tmp_path, "kept_but_doc_says_dropped")
    complete.patch(
        target / "docs" / "readers" / "sjs.md",
        "보내던 쪽이 sjl로 옮겨 가는 중이지만 **표본이 계속 들어오므로 v0.4에서도\n"
        "받는다.** 들어오지 않게 되면 그때 뺀다.",
        "**이 원천은 v0.4부터 받지 않기로 했다.** 보내던 쪽이 sjl로 옮겨 갔다.")

    assert grade.checkpoints(target)["dropped_source.settled"] is False
