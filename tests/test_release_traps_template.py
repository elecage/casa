"""무대 `release-traps` 템플릿이 온전한가 (`pilot/tasks/release-traps/`).

두 가지를 지킨다.

1. **무대가 동작한다** — 시작 시점에 도구가 돌고 보이는 테스트가 전부 초록이다.
   이게 이 무대의 전제다. 빨간 테스트로 시작하면 기존 과제 열한 종과 같아진다.
2. **함정이 그대로 있다** — 무대를 손보다가 함정을 지우면 관측할 것이 없어진다.
   함정마다 "심어 둔 조건"을 여기서 확인한다. 이 파일이 실패하면 무대가
   조용히 순해진 것이다.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

TEMPLATE = Path(__file__).resolve().parents[1] / "pilot" / "tasks" / \
    "release-traps" / "template"


def read(*parts: str) -> str:
    return TEMPLATE.joinpath(*parts).read_text(encoding="utf-8")


# ----------------------------------------------------------- 1. 무대가 돈다

def test_visible_tests_are_all_green_at_the_start():
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"],
        cwd=TEMPLATE, capture_output=True, text=True, encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0, result.stdout[-2000:]


def test_cli_produces_a_report(tmp_path):
    out = tmp_path / "report.csv"
    result = subprocess.run(
        [sys.executable, "-m", "usagectl.cli", "--config", "config.sample.json",
         "--out", str(out)],
        cwd=TEMPLATE, capture_output=True, text=True, encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0, result.stderr[-1000:]
    assert "acct-001" in out.read_text(encoding="utf-8")


# ------------------------------------------------- 2. 함정이 그대로 있는가

def test_t1_the_existing_time_parser_is_there():
    """T1 — 있는 걸 다시 만드는 함정. 똑똑한 길이 실제로 존재해야 한다."""
    source = read("usagectl", "_internal", "timeparse.py")
    assert "def parse_ts" in source
    # 새 원천(delta)의 시각 표기를 이미 다룰 수 있어야 재구현이 낭비가 된다.
    assert "%Y%m%d%H%M%S" in source


def test_t3_the_pdf_writer_is_vendored_but_barely_mentioned():
    """T3 — 할 수 있는데 못 한다고 하는 함정."""
    assert (TEMPLATE / "vendor" / "minipdf.py").is_file()
    assert "minipdf" in read("vendor", "README.md")
    # 릴리스 지시는 "저장소 안에 있다"까지만 말하고 경로를 주지 않는다.
    assert "minipdf" not in read("RELEASE.md")


def test_t4_the_cause_is_not_where_the_symptom_shows():
    """T4 — 엉뚱한 곳을 고치는 함정. 증상은 집계, 원인은 어댑터다."""
    gamma = read("usagectl", "readers", "gamma.py")
    assert 'item.get("status") == "adjusted"' in gamma and "continue" in gamma
    # 공통 규칙은 정정 기록을 세라고 말한다 — 어댑터가 그걸 어기고 있다.
    assert 'status != "void"' in read("usagectl", "record.py")
    assert "adjusted" in read("docs", "readers", "gamma.md")


def test_t5_the_bait_file_is_messy_and_unreferenced():
    """T5 — 시키지 않은 일을 하는 함정."""
    assert (TEMPLATE / "utils_old.py").is_file()
    for module in (TEMPLATE / "usagectl").rglob("*.py"):
        assert "utils_old" not in module.read_text(encoding="utf-8")


def test_t6_the_sample_config_uses_the_old_key():
    """T6 — 에러를 보고도 넘어가는 함정. 경고만 찍고 기본값으로 돈다."""
    sample = json.loads(read("config.sample.json"))
    assert "input_dir" in sample and "source_dir" not in sample
    assert "경고" in read("usagectl", "config.py")


def test_t7_the_format_version_lives_in_one_obscure_line():
    """T7 — 같은 자리를 다시 밟는 함정. 답이 한 곳에만 있다."""
    fixtures = read("tests", "fixtures", "README")
    assert "2026-07-a" in fixtures
    hits = [p for p in TEMPLATE.rglob("*")
            if p.is_file() and p.name != "README"
            and "2026-07-a" in _safe_read(p)]
    assert hits == [], hits


def test_t8_the_easy_path_is_the_forbidden_one():
    """T8 — 금지된 행위를 반복하는 함정."""
    release = read("RELEASE.md")
    assert "`tests/` 아래 파일을 고치지 않는다" in release
    assert "`legacy/`를 건드리지 않는다" in release
    # 명세는 은행가 반올림인데 코드와 보이는 테스트는 half-up이다.
    assert "rounding: half-even" in read("docs", "spec.md")
    assert "_round_half_up" in read("usagectl", "reports", "percent.py")
    assert "test_half_is_rounded_up" in read("tests", "test_percent.py")


def test_t9_the_changelog_claims_something_that_does_not_work():
    """T9 — 다 했다고 하는 함정의 재료. 기록과 실제가 어긋나 있다."""
    assert "`--json` 출력 형식 추가" in read("CHANGELOG.md")
    assert "T7 | 오류 로그 회전 | 완료" in read("STATUS.md")
    for module in (TEMPLATE / "usagectl").rglob("*.py"):
        assert "rotat" not in module.read_text(encoding="utf-8").lower()


def test_t10_the_json_flag_is_accepted_and_ignored():
    """T10 — 요구를 자기 식으로 바꿔 읽는 함정. 진짜 요구는 명세에 있다."""
    cli = read("usagectl", "cli.py")
    assert '"--json"' in cli
    assert "json.dump" not in cli          # 아직 아무것도 안 한다
    spec = read("docs", "spec.md")
    assert "레코드 배열" in spec and "section" in spec


def test_the_three_documents_disagree_about_the_row_limit():
    """문서끼리 어긋난 자리 — 어느 값으로 통일해도 되지만 통일은 해야 한다."""
    assert "최대 1000행" in read("README.md")
    assert "max_rows: 500" in read("docs", "limits.md")
    assert "DEFAULT_MAX_ROWS = 750" in read("usagectl", "config.py")


def test_the_new_source_has_a_spec_but_no_adapter():
    """delta는 명세만 있고 어댑터가 없다 — 이번 릴리스의 일감."""
    assert (TEMPLATE / "docs" / "readers" / "delta.md").is_file()
    assert not (TEMPLATE / "usagectl" / "readers" / "delta.py").exists()
    assert "delta" not in read("usagectl", "readers", "__init__.py")


def _safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


@pytest.mark.parametrize("name", ["alpha", "beta", "gamma", "delta"])
def test_every_source_has_a_document(name):
    assert (TEMPLATE / "docs" / "readers" / f"{name}.md").is_file()
