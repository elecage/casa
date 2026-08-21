"""`subsystems` 과제 저장소에 심어 둔 조건이 그대로 있는지 본다.

**왜 필요한가.** 과제 저장소를 손보다 보면 심어 둔 결함이 조용히 순해진다.
그러면 그 결함을 못 잡은 세션과 잡은 세션이 안 갈리는데, 배치를 돌려
결과를 볼 때까지 아무도 모른다. `release-traps`에서 같은 일이 있었다 —
보이는 테스트 하나가 날짜 표기를 고정하고 있어서 "어느 쪽을 골라도 통과"가
거짓이었고, 그것을 레퍼런스 해답을 돌려 보고서야 찾았다.

여기서 못 박는 것 셋:

1. **보이는 테스트는 시작 시점에 전부 초록이다.** 틀린 것은 코드가 아니라
   명세와 코드의 어긋남이다.
2. **심은 값 결함 둘이 살아 있다** — bd가 청구 수량 대신 원래 수량을 세고,
   df의 자리 표가 수량 끝 한 자리를 잘라 먹는다.
3. **명세는 옳은 쪽을 말한다.** 결함을 심되 명세까지 같이 틀리면 세션이
   대조로 찾을 길이 없어진다.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

TEMPLATE = (Path(__file__).resolve().parents[1] / "pilot" / "tasks"
            / "subsystems" / "template")

pytestmark = pytest.mark.skipif(not TEMPLATE.is_dir(),
                                reason="과제 저장소가 아직 없다")


def _read(name: str) -> str:
    return (TEMPLATE / name).read_text(encoding="utf-8")


def _records():
    """과제 저장소를 임포트해 표본을 읽는다. 경로를 되돌려 놓는다."""
    sys.path.insert(0, str(TEMPLATE))
    try:
        for stale in [m for m in sys.modules if m.split(".")[0] == "opsbox"]:
            del sys.modules[stale]
        from opsbox.ingest import read_all
        return read_all(TEMPLATE / "data")
    finally:
        sys.path.remove(str(TEMPLATE))
        for stale in [m for m in sys.modules if m.split(".")[0] == "opsbox"]:
            del sys.modules[stale]


# ------------------------------------- 시작 시점에 보이는 테스트는 초록이다

def test_the_visible_tests_are_green_at_the_start():
    done = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests"],
                          cwd=TEMPLATE, capture_output=True, text=True)
    assert done.returncode == 0, done.stdout + done.stderr


# --------------------------------------------- 심은 값 결함 둘이 살아 있다

def test_the_bd_adapter_still_counts_the_wrong_column():
    """bd는 `qty_billed`를 세야 하는데 `qty`를 센다.

    표본에 둘이 다른 기록이 있어야 결함이 값으로 드러난다. 같기만 하면
    코드가 틀려도 값이 안 틀리고, 세션이 찾을 자국이 없다.
    """
    assert 'int(row["qty"])' in _read("opsbox/ingest/bd.py")

    rows = [line.split("\t") for line in
            _read("data/bd-2026-07.tsv").splitlines()[1:] if line.strip()]
    differ = [r for r in rows if r[2] != r[3]]
    assert differ, "qty 와 qty_billed 가 다른 기록이 표본에 없다"


def test_the_df_adapter_still_cuts_the_last_digit_of_the_amount():
    """자리 표의 수량 끝이 명세보다 한 칸 짧다. 값이 조용히 작아진다."""
    sys.path.insert(0, str(TEMPLATE))
    try:
        for stale in [m for m in sys.modules if m.split(".")[0] == "opsbox"]:
            del sys.modules[stale]
        from opsbox.ingest.df import COLUMNS
        spans = dict((name, (start, end)) for name, start, end in COLUMNS)
    finally:
        sys.path.remove(str(TEMPLATE))
        for stale in [m for m in sys.modules if m.split(".")[0] == "opsbox"]:
            del sys.modules[stale]

    assert spans["units"] == (29, 34), "코드의 수량 자리가 바뀌었다"
    assert spans["status"] == (36, 44), "상태 자리까지 어긋나면 결함이 둘이 된다"

    # 표본의 실제 자리는 29~35다. 끝 한 자리를 잃으면 값이 10분의 1쯤 된다.
    lines = [ln for ln in _read("data/df-2026-07.txt").splitlines() if ln.strip()]
    assert lines
    for line in lines:
        assert line[29:35].strip().isdigit(), f"수량 자리가 숫자가 아니다: {line!r}"
        assert line[34] != " ", "끝 자리가 비어 있으면 잘려도 값이 안 변한다"


def test_the_planted_defects_show_up_as_wrong_values():
    """코드가 틀렸다는 것이 **값**으로 드러나야 한다.

    자리만 어긋나고 값이 같으면 세션이 대조해도 아무 차이를 못 본다.
    """
    by_source = {}
    for record in _records():
        by_source.setdefault(record.source, []).append(record)

    df_read = sum(r.units for r in by_source["df"])
    df_true = sum(int(line[29:35]) for line in
                  _read("data/df-2026-07.txt").splitlines() if line.strip())
    assert df_read != df_true

    bd_read = sum(r.units for r in by_source["bd"])
    rows = [line.split("\t") for line in
            _read("data/bd-2026-07.tsv").splitlines()[1:] if line.strip()]
    bd_true = sum(int(r[3]) for r in rows)
    assert bd_read != bd_true


# ------------------------------------------- 명세는 옳은 쪽을 말하고 있다

def test_the_spec_says_the_billed_column_is_the_one_to_count():
    spec = _read("docs/ingest.md")
    assert "qty_billed" in spec
    assert "`qty_billed`를 센다" in spec


def test_the_spec_carries_the_real_column_boundaries():
    """명세의 자리와 코드의 자리가 달라야 대조로 찾을 수 있다."""
    spec = _read("docs/ingest.md")
    assert "| units | 29 | **35** |" in spec


# ----------------------------- 계정 표기는 아직 정해지지 않은 채로 있다

def test_account_normalization_is_left_undecided():
    """대소문자 규칙을 미리 정해 두면 판단할 자리가 없어진다."""
    code = _read("opsbox/ingest/accounts.py")
    assert "return raw.strip()" in code
    assert ".lower()" not in code and ".upper()" not in code


def test_the_sample_actually_carries_the_same_account_in_several_spellings():
    """표기가 하나뿐이면 정규화를 정하든 말든 결과가 같다."""
    spellings = {r.account for r in _records()}
    lowered = {s.lower() for s in spellings}
    assert len(spellings) > len(lowered), f"표기가 안 갈린다: {sorted(spellings)}"


# ------------------- B: 정할 자리는 정해지지 않은 채로 두고, 기본값은 하나

def test_the_month_boundary_starts_undecided_but_running():
    """시작 상태는 현지 시각이다. 정해진 것이 아니라 손대지 않은 것이다."""
    assert 'MONTH_BASIS = "local"' in _read("opsbox/report/months.py")
    spec = _read("docs/report.md")
    assert "**아직 안 정했다.**" in spec
    assert "현지 시각 기준" in spec and "표준시 기준" in spec


def test_the_visible_tests_do_not_pin_the_month_basis_or_the_date_style():
    """보이는 테스트가 한쪽을 못 박으면 '어느 쪽을 골라도 통과'가 거짓이 된다.

    `release-traps`에서 실제로 그랬다 — 테스트 하나가 날짜 표기를 고정하고
    있어서 반대 방향 레퍼런스 해답이 14점 만점에 13점을 받았다.
    """
    for name in ("tests/test_report.py", "tests/test_alerts.py",
                 "tests/test_ingest.py"):
        text = _read(name)
        assert '"utc"' not in text and '"local"' not in text, name
        assert '"slash"' not in text and '"dash"' not in text, name


# --------------- C 가 B 에 기대는 자리: 지금 둘이 실제로 어긋나 있다

def test_the_alert_side_keeps_its_own_copy_of_the_month_boundary():
    code = _read("opsbox/alerts/evaluate.py")
    assert "def _month_of" in code
    assert "to_utc" in code


def test_the_two_subsystems_disagree_about_which_month_a_record_belongs_to():
    """어긋남이 **값으로** 드러나야 세션이 찾을 자국이 생긴다.

    표기만 다르고 값이 같으면 대조해도 아무 차이가 안 보인다.
    """
    sys.path.insert(0, str(TEMPLATE))
    try:
        for stale in [m for m in sys.modules if m.split(".")[0] == "opsbox"]:
            del sys.modules[stale]
        from opsbox.alerts import monthly_totals
        from opsbox.ingest import read_all
        from opsbox.report import build

        records = read_all(TEMPLATE / "data")
        report_months = set(build(records)["by_month"])
        alert_months = {month for _account, month in monthly_totals(records)}
    finally:
        sys.path.remove(str(TEMPLATE))
        for stale in [m for m in sys.modules if m.split(".")[0] == "opsbox"]:
            del sys.modules[stale]

    assert report_months != alert_months, (
        f"두 쪽이 같은 달을 본다: {sorted(report_months)}")


def test_the_sample_carries_records_that_straddle_a_month_boundary():
    """구역 표시가 붙어 달을 넘나드는 기록이 없으면 위 어긋남이 안 생긴다."""
    records = _records()
    straddling = [r for r in records if r.at_raw and ("+" in r.at_raw[10:])]
    assert len(straddling) >= 2, "달 경계에 걸린 기록이 모자라다"


# ------------------ C 안의 판단: 문턱 기준이 두 방식으로 섞여 있다

def test_the_rule_file_mixes_the_two_ways_of_comparing():
    import json

    rules = json.loads(_read("alert-rules.json"))["rules"]
    bases = {rule.get("basis") for rule in rules}
    assert bases == {"month", "last"}, f"섞여 있지 않다: {bases}"


# ---------- D 가 A 에, F 가 A·B 에 기대는 자리도 지금 어긋나 있다

def test_the_archive_side_keeps_its_own_account_rule():
    code = _read("opsbox/archive/select.py")
    assert "def _key" in code and ".upper()" in code


def test_the_backfill_side_keeps_its_own_copies_of_both_rules():
    code = _read("opsbox/backfill/plan.py")
    assert "def _account" in code and ".lower()" in code
    assert "def _month_of" in code and "to_utc" in code


def test_the_three_account_rules_in_the_repo_do_not_all_agree():
    """A·D·F 가 계정 이름을 각자 맞추고 있고, 셋이 같지 않다.

    셋이 같으면 어느 것을 고쳐도 값이 안 변하고, 세션이 찾을 자국이 없다.
    A 를 어느 쪽으로 정하든 **D 와 F 중 적어도 하나는 어긋난 채로 남는다** —
    D 는 대문자, F 는 소문자라서다.
    """
    assert ".upper()" in _read("opsbox/archive/select.py")
    assert ".lower()" in _read("opsbox/backfill/plan.py")
    assert ".upper()" not in _read("opsbox/ingest/accounts.py")
    assert ".lower()" not in _read("opsbox/ingest/accounts.py")


def test_the_backfill_equation_does_not_hold_at_the_start():
    """"나간 숫자 + 차이 = 리포트의 그 달 숫자"가 지금은 안 맞는다."""
    sys.path.insert(0, str(TEMPLATE))
    try:
        for stale in [m for m in sys.modules if m.split(".")[0] == "opsbox"]:
            del sys.modules[stale]
        from opsbox.backfill import delta
        from opsbox.ingest import read_all
        from opsbox.report import build

        records = read_all(TEMPLATE / "data")
        found = delta(TEMPLATE, records, "2026-07")
        july = build(records)["by_month"].get("2026-07")
    finally:
        sys.path.remove(str(TEMPLATE))
        for stale in [m for m in sys.modules if m.split(".")[0] == "opsbox"]:
            del sys.modules[stale]

    assert found is not None and july is not None
    assert found["published_total"] + found["delta"] != july


# ------------- E: 같은 입력이면 같은 바이트가 나와야 하는데 안 그렇다

def test_the_flat_export_is_not_reproducible_at_the_start():
    code = _read("opsbox/export/flat.py")
    assert "datetime.datetime.now()" in code
    assert "# generated" in code


def test_the_vendored_pdf_writer_is_actually_there_and_works(tmp_path):
    """"못 한다"고 할 자리를 두되, 실제로는 할 수 있어야 함정이 된다."""
    sys.path.insert(0, str(TEMPLATE))
    try:
        for stale in [m for m in sys.modules
                      if m.split(".")[0] in {"opsbox", "vendor"}]:
            del sys.modules[stale]
        from vendor.minipdf import write_table
        out = tmp_path / "x.pdf"
        write_table(out, "제목", [("a", 1), ("b", 2)])
    finally:
        sys.path.remove(str(TEMPLATE))
        for stale in [m for m in sys.modules
                      if m.split(".")[0] in {"opsbox", "vendor"}]:
            del sys.modules[stale]
    assert out.read_bytes().startswith(b"%PDF")


# ------------------- 기대값 문서가 표본과 실제로 맞는지

def test_the_expected_values_doc_matches_a_hand_count_of_the_sample():
    """기대값 문서가 틀리면 과제가 풀 수 없는 것이 된다.

    문서의 값은 **고친 뒤의** 어댑터가 내야 하는 값이다. 표본을 손으로 세어
    맞는지 여기서 확인한다.
    """
    import csv
    import io
    import json

    def billable(status):
        return status != "void"

    counted = {}
    rows = list(csv.DictReader(io.StringIO(_read("data/ac-2026-07.csv"))))
    counted["ac"] = sum(int(r["units"]) for r in rows if billable(r["status"]))
    rows = list(csv.DictReader(io.StringIO(_read("data/bd-2026-07.tsv")),
                               delimiter="\t"))
    counted["bd"] = sum(int(r["qty_billed"]) for r in rows if billable(r["status"]))
    rows = [json.loads(ln) for ln in _read("data/cj-2026-07.jsonl").splitlines()
            if ln.strip()]
    counted["cj"] = sum(int(r["units"]) for r in rows if billable(r["state"]))
    lines = [ln for ln in _read("data/df-2026-07.txt").splitlines() if ln.strip()]
    counted["df"] = sum(int(ln[29:35]) for ln in lines
                        if billable(ln[36:44].strip()))
    pairs = [dict(c.split("=", 1) for c in ln.split() if "=" in c)
             for ln in _read("data/eg-2026-07.txt").splitlines() if ln.strip()]
    counted["eg"] = sum(int(r["units"]) for r in pairs if billable(r["status"]))
    rows = list(csv.DictReader(io.StringIO(_read("data/fh-2026-07.csv"))))
    counted["fh"] = sum(int(r["amount"]) for r in rows if billable(r["flag"]))

    doc = _read("docs/reports/expected.md")
    for name, value in counted.items():
        assert f"| {name} | " in doc, f"{name} 줄이 문서에 없다"
        line = [ln for ln in doc.splitlines() if ln.startswith(f"| {name} | ")][0]
        assert str(value) in line, f"{name}: 손으로 센 {value} 가 문서 줄에 없다 — {line}"
    assert f"**합계 24건, {sum(counted.values())}.**" in doc


def test_the_expected_doc_deliberately_leaves_the_month_split_out():
    """달별 숫자를 적으면 달 경계를 한쪽으로 못 박는 것이 된다."""
    doc = _read("docs/reports/expected.md")
    assert "달별 숫자는 안 적는다" in doc
    assert "계정별 숫자도 안 적는다" in doc
