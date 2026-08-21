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
