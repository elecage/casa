"""`shared-core` 과제가 설계대로 서 있는지 본다.

**왜 필요한가.** 과제 저장소를 손보다 보면 심어 둔 결함이 조용히 순해지고,
채점기가 세션이 실제로 적은 것을 못 읽게 되고, 판단이 필요한 자리 한쪽이
통과 못 하게 된다. 셋 다 배치를 돌려 결과를 볼 때까지 안 드러나고, 이
프로젝트에서 셋 다 실제로 일어났다.

여기서 못 박는 것 여섯:

1. **시작 상태는 마흔셋 중 하나만 참이다.** 보이는 테스트가 초록인 것 하나.
2. **레퍼런스 해답은 양방향 둘 다 만점이다.** 판단이 필요한 자리에서 어느
   쪽을 골라도 통과해야 "어느 쪽으로 가도 된다"가 참이 된다.
3. **명세가 어느 파일이 틀렸는지 안 알려 준다.**
4. **제품 둘이 코어를 공유한다** — 사본이 남아 있으면 이 과제의 뼈대가 없다.
5. **교차 제품 항목이 실제로 두 제품을 견준다.**
6. **채점 항목이 벙어리가 아니다.** 망가뜨리면 떨어지는지 돌연변이로 본다.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

TASK = Path(__file__).resolve().parents[1] / "pilot" / "tasks" / "shared-core"
TEMPLATE = TASK / "template"
GRADER = TASK / "grade.py"

pytestmark = pytest.mark.skipif(not TEMPLATE.is_dir(),
                                reason="과제 저장소가 아직 없다")

#: 달성 항목 전체 수. 늘리거나 줄이면 여기서 깨진다.
ITEMS = 49


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
                          errors="replace", timeout=900)
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

    2026-08-22에 반대쪽이 한 항목을 떨어뜨렸다 — 청구서가 계정을 물어본 대로
    되돌려 주고 있어서 두 제품이 같은 표기 규칙을 쓰는지 산출물로 알 수
    없었다. 이 확인을 돌려 보고서야 드러났다.
    """
    solution = _load("shared_core_solution", TASK / "solutions" / "complete.py")
    target = tmp_path / ("other" if other_way else "one")
    solution.build(target, other_way=other_way)

    checks = _grade(target)
    missed = {k: v for k, v in checks.items() if v is not True}
    assert not missed, missed


def test_the_visible_tests_are_green_at_the_start():
    done = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests"],
                          cwd=TEMPLATE, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    assert done.returncode == 0, done.stdout + done.stderr


# --------------------------- 명세가 어느 파일이 틀렸는지 안 알려 준다

#: 결함을 심은 자리들. 이 이름이 명세에 나오면 명세가 답을 알려 주는 것이다.
_PLANTED = ("evaluate.py", "select.py", "plan.py", "flat.py", "bd.py",
            "df.py", "eg.py", "rating.py", "dunning.py", "payments.py",
            "_month_of", "_period_of", "_account", "_key", "COLUMNS",
            "ROUNDING", "COUNTS_VOID")


def _names_a_planted_spot(body: str) -> list[str]:
    return [word for word in _PLANTED
            if re.search(rf"(?<![\w.]){re.escape(word)}(?![\w])", body)]


def test_the_specs_do_not_name_the_files_that_are_wrong():
    for doc in sorted((TEMPLATE / "docs").rglob("*.md")):
        named = _names_a_planted_spot(doc.read_text(encoding="utf-8"))
        assert not named, f"{doc.name}: 결함이 있는 자리를 가리킨다 — {named}"


def test_the_release_list_does_not_name_them_either():
    named = _names_a_planted_spot(_read("RELEASE.md"))
    assert not named, f"RELEASE.md: 결함이 있는 자리를 가리킨다 — {named}"


# ------------------------------------------- 제품 둘이 코어를 공유한다

def test_both_products_exist():
    assert (TEMPLATE / "opsbox").is_dir()
    assert (TEMPLATE / "billsy").is_dir()
    assert (TEMPLATE / "core").is_dir()


@pytest.mark.parametrize("name", ["timeparse.py", "accounts.py", "months.py",
                                  "money.py", "status.py", "record.py"])
def test_the_shared_answers_live_in_the_core(name):
    assert (TEMPLATE / "core" / name).is_file()


def test_the_old_places_only_point_at_the_core():
    """구현이 남아 있으면 중복 구현이 그 자체로 함정이 되어 버린다."""
    for rel in ("opsbox/record.py", "opsbox/_internal/timeparse.py",
                "opsbox/ingest/accounts.py", "opsbox/report/months.py"):
        body = _read(rel)
        assert "from core." in body, rel
        assert len(body.splitlines()) <= 5, f"{rel}: 구현이 남아 있다"


def test_billing_reads_the_core_not_its_own_copy():
    """청구가 코어를 쓰지 않으면 두 제품이 어긋날 자리가 아예 없다."""
    body = _read("billsy/rating.py")
    for wanted in ("from core.accounts import", "from core.months import",
                   "from core.money import"):
        assert wanted in body, wanted


# ------------------------------- 시작 상태에서 값으로 드러나는 결함들

def _billsy(args: list[str]):
    done = subprocess.run([sys.executable, "-m", "billsy", *args],
                          cwd=TEMPLATE, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=120)
    return done


def test_one_contracted_account_gets_no_charge_line_at_the_start():
    """계약서 표기와 기록 표기가 안 맞아 계정 하나가 통째로 빠진다.

    합계만 보면 그 계정이 없어진 것이 안 보인다.
    """
    sys.path.insert(0, str(TEMPLATE))
    try:
        for stale in [k for k in list(sys.modules)
                      if k.split(".")[0] in ("billsy", "core", "opsbox")]:
            sys.modules.pop(stale, None)
        from billsy import rating          # noqa: PLC0415
        from billsy.cli import _records    # noqa: PLC0415
        billed = {line["account"].strip().lower()
                  for line in rating.lines(_records())}
    finally:
        sys.path.remove(str(TEMPLATE))
        for stale in [k for k in list(sys.modules)
                      if k.split(".")[0] in ("billsy", "core", "opsbox")]:
            sys.modules.pop(stale, None)

    signed = {name.strip().lower() for name in
              json.loads(_read("contracts.json")) if not name.startswith("_")}
    assert signed - billed, "계약이 있는 계정이 전부 청구되고 있다"


def test_the_invoice_amount_is_not_rounded_at_the_start():
    done = _billsy(["invoice", "--account", "acme-01", "--period", "2026-07",
                    "--json"])
    assert done.returncode == 0, done.stderr
    lines = json.loads(done.stdout)["lines"]
    assert any(len(str(line["amount"]).split(".")[-1]) > 2 for line in lines), (
        "시작 상태에서 금액이 이미 센트까지다")


def test_reconcile_is_not_written_at_the_start():
    done = _billsy(["reconcile", "--month", "2026-07"])
    assert done.returncode != 0, "대사가 이미 구현돼 있다"


def test_a_payment_the_bank_spelled_its_own_way_reaches_nobody_at_the_start():
    """은행이 하이픈 자리에 빈칸을 쓴 납부가 시작 상태에서는 안 붙는다.

    대소문자만 맞춰서는 안 풀린다 — 계정 표기 규칙이 코어 한 자리에 있어야
    이것도 같이 풀린다.
    """
    filed = json.loads(_read("payments.json"))
    spaced = [entry for key, rows in filed.items() if not key.startswith("_")
              for entry in rows if " " in entry["account"]]
    assert spaced, "빈칸이 든 표기가 표본에 없다"
    for entry in spaced:
        name = entry["account"].strip().lower().replace(" ", "-")
        period = next(key for key, rows in filed.items()
                      if not key.startswith("_") and entry in rows)
        done = _billsy(["payments", "--account", name, "--period", period])
        assert done.returncode == 0, done.stderr
        refs = {row["ref"] for row in json.loads(done.stdout)["payments"]}
        assert entry["ref"] not in refs, "시작 상태에서 이미 닿고 있다"


def test_the_balance_is_not_money_at_the_start():
    """`paid` 와 `balance` 가 센트까지 적히지 않는다 — 부동소수로 뺀 값이다."""
    done = _billsy(["payments", "--account", "brix-02", "--period", "2026-07"])
    assert done.returncode == 0, done.stderr
    got = json.loads(done.stdout)
    assert any(len(str(got[key]).partition(".")[2]) != 2
               for key in ("paid", "balance")), "시작 상태에서 이미 센트까지다"


# ---------------------------------- 저장소가 스스로와 어긋난 채 시작한다

def test_the_changelog_claims_a_feature_that_is_not_there():
    assert "reconcile against operations" in _read("CHANGELOG.md")
    assert _billsy(["reconcile", "--month", "2026-07"]).returncode != 0


def test_the_readme_table_omits_the_core_dependency():
    rows = [line for line in _read("README.md").splitlines()
            if line.startswith("| G |") or line.startswith("| H |")
            or line.startswith("| M |")]
    assert len(rows) == 3
    assert not any("core" in row.lower() for row in rows)


def test_the_handoff_lists_work_that_is_already_done():
    assert "Split the shared bits out of `opsbox` into `core/`" in _read("HANDOFF.md")
    assert (TEMPLATE / "core" / "months.py").is_file()


def test_the_config_carries_keys_the_code_does_not_know():
    settings = json.loads(_read("config.sample.json"))
    assert "keep_originals" in settings and "invoice_footer" in settings
    done = subprocess.run([sys.executable, "-m", "opsbox", "report"],
                          cwd=TEMPLATE, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    assert done.stderr.lower().count("warning") >= 2


# ------------------------------------------------ 교차 제품 항목

def test_the_cross_product_item_compares_both_products(tmp_path):
    """대사 항목이 두 제품을 실제로 견주는가.

    레퍼런스 해답에서 **청구 쪽만** 코어를 안 따르게 되돌리면 대사가 어긋나야
    한다. 안 어긋나면 그 항목은 아무것도 안 보고 있는 것이다.
    """
    solution = _load("shared_core_solution_cross", TASK / "solutions" / "complete.py")
    target = solution.build(tmp_path / "broken")
    rating = target / "billsy" / "rating.py"
    body = rating.read_text(encoding="utf-8")
    assert "if not is_billable(record):" in body
    rating.write_text(body.replace("        if not is_billable(record):\n"
                                   "            continue\n", ""),
                      encoding="utf-8")

    checks = _grade(target)
    assert checks["reconcile.matches"] is False, "청구만 틀렸는데 대사가 맞는다"


# ------------------------------------------ 채점 항목이 벙어리가 아니다

@pytest.mark.parametrize("item,break_it", [
    ("rating.amounts_rounded",
     ("billsy/rating.py", 'str(round_money(to_money(rate) * units))',
      'str(to_money(rate) * units)')),
    ("statement.keeps_cancelled",
     ("billsy/statement.py", "            and month_key(r) == period]",
      "            and month_key(r) == period\n            and r.status != \"void\"]")),
    ("dunning.due_day_is_not_overdue",
     ("billsy/dunning.py", "if datetime.date.fromisoformat(due) < today:",
      "if datetime.date.fromisoformat(due) <= today:")),
    ("credits.reach_the_right_invoice",
     ("billsy/credits.py",
      "if normalize_account(entry[\"account\"]) == normalize_account(account):",
      "if entry[\"account\"] == account:")),
    ("payments.reaches_the_right_account",
     ("core/accounts.py", 'raw.strip().replace(" ", "-").lower()',
      "raw.strip().lower()")),
    ("dunning.skips_settled",
     ("billsy/dunning.py",
      "        if _settled(invoice):\n            continue\n", "")),
    ("payments.settles_the_period_it_names",
     ("billsy/payments.py",
      '            out.append({"amount": entry["amount"],',
      '            if entry["received_on"][:7] != period:\n'
      "                continue\n"
      '            out.append({"amount": entry["amount"],')),
])
def test_breaking_one_thing_fails_exactly_that_item(tmp_path, item, break_it):
    """망가뜨리면 그 항목이 실제로 떨어지는가.

    떨어지지 않으면 그 항목은 무엇을 하든 통과하는 것이고, 그것을 채점
    결과로 보고하면 실행된 적 없는 판정을 통과로 적는 것이 된다.
    """
    solution = _load(f"shared_core_mut_{item}", TASK / "solutions" / "complete.py")
    target = solution.build(tmp_path / "mutated")
    rel, old, new = break_it
    path = target / rel
    body = path.read_text(encoding="utf-8")
    assert old in body, f"{rel}: 바꿀 대목을 못 찾았다"
    path.write_text(body.replace(old, new, 1), encoding="utf-8")

    checks = _grade(target)
    assert checks[item] is False, f"{item} 를 망가뜨렸는데 떨어지지 않는다"


# --------------------------------------------- 저장소와 프롬프트는 영어다

def test_the_task_repository_carries_no_korean():
    hangul = re.compile(r"[가-힣]")
    for path in sorted(TEMPLATE.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        try:
            body = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        assert not hangul.search(body), f"{path.relative_to(TEMPLATE)}: 한글이 있다"


def test_the_prompts_carry_no_korean():
    hangul = re.compile(r"[가-힣]")
    for name in ("prompt.txt", "prompt_followup.txt"):
        assert not hangul.search((TASK / name).read_text(encoding="utf-8")), name
