#!/usr/bin/env python3
"""레퍼런스 해답 — 달성 항목 열일곱을 다 채운다.

**무엇에 쓰나.** 과제가 풀 수 있는 것인지, 그리고 **판단이 필요한 항목이
정말로 양쪽 다 통과하는지**를 기계로 확인한다. 세션에게 주는 것이 아니다.

`--other-way`를 주면 판단이 필요한 자리마다 **반대쪽**을 고른다. 두 벌 다
열일곱을 채워야 "어느 쪽을 골라도 된다"가 참이다. 2026-08-21에
`release-traps`에서 이것이 거짓이었다 — 보이는 테스트 하나가 날짜 표기를
고정하고 있어서 반대쪽 해답이 한 항목을 떨어뜨렸고, 이 확인을 돌려 보고서야
알았다.

사용:

    python solutions/complete.py <대상 디렉토리> [--other-way]
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE.parent / "template"


def _edit(path: Path, old: str, new: str, *, count: int = 1) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"{path.name}: 바꿀 대목을 못 찾았다 — {old[:40]!r}")
    path.write_text(text.replace(old, new, count), encoding="utf-8")


def _append_after(path: Path, anchor: str, line: str) -> None:
    text = path.read_text(encoding="utf-8")
    if anchor not in text:
        raise SystemExit(f"{path.name}: 기준 대목을 못 찾았다")
    head, _, tail = text.partition(anchor)
    path.write_text(head + anchor + "\n\n" + line + tail, encoding="utf-8")


def build(target: Path, other_way: bool = False) -> Path:
    """과제 저장소를 베끼고 열일곱 항목을 다 채운다."""
    target = Path(target)
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(TEMPLATE, target,
                    ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))

    # 판단이 필요한 자리마다 어느 쪽을 고를지.
    case = "upper" if other_way else "lower"
    basis = "utc" if other_way else "local"
    style = "slash" if other_way else "dash"
    alert_basis = "last" if other_way else "month"
    pick = "size" if other_way else "age"
    stable = "asof" if other_way else "drop"

    # ---------------------------------------------- A 입력 어댑터
    # bd: 청구 수량을 센다.
    _edit(target / "opsbox/ingest/bd.py", 'int(row["qty"])', 'int(row["qty_billed"])')
    # df: 자리 표를 명세대로 고친다.
    _edit(target / "opsbox/ingest/df.py", '("units", 29, 34),', '("units", 29, 35),')
    # 계정 표기를 정한다.
    _edit(target / "opsbox/ingest/accounts.py", "    return raw.strip()",
          f"    return raw.strip().{case}()")
    _append_after(target / "docs/ingest.md", "## 계정 표기",
                  f"결정: {'대문자' if case == 'upper' else '소문자'}\n")

    # ---------------------------------------------- B 집계와 리포트
    _edit(target / "opsbox/report/months.py", 'MONTH_BASIS = "local"',
          f'MONTH_BASIS = "{basis}"')
    _append_after(target / "docs/report.md", "## 달 경계",
                  f"결정: {'표준시' if basis == 'utc' else '현지 시각'}\n")
    _edit(target / "opsbox/report/dates.py", 'DATE_STYLE = "dash"',
          f'DATE_STYLE = "{style}"')
    _append_after(target / "docs/report.md", "## 날짜 표기",
                  f"결정: {'빗금' if style == 'slash' else '붙임표'}\n")

    # ---------------------------------------------- C 알림 규칙
    # 달 경계를 리포트에서 가져온다. 자기 사본을 지운다.
    _edit(target / "opsbox/alerts/evaluate.py",
          "from .._internal.timeparse import to_utc\nfrom ..record import is_billable",
          "from ..record import is_billable\nfrom ..report.months import month_key")
    evaluate = target / "opsbox/alerts/evaluate.py"
    text = evaluate.read_text(encoding="utf-8")
    start = text.index("def _month_of(record) -> str:")
    end = text.index("def monthly_totals")
    text = text[:start] + text[end:]
    text = text.replace("_month_of(record)", "month_key(record)")
    evaluate.write_text(text, encoding="utf-8")
    # 문턱 기준을 하나로 모은다.
    rules_path = target / "alert-rules.json"
    raw = json.loads(rules_path.read_text(encoding="utf-8"))
    for rule in raw["rules"]:
        rule["basis"] = alert_basis
    rules_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
    _append_after(target / "docs/alerts.md", "## 지금 규칙 파일이 두 방식으로 섞여 있다",
                  f"결정: {'마지막 관측' if alert_basis == 'last' else '그 달 전체'}\n")

    # ---------------------------------------------- D 보관과 정리
    _edit(target / "opsbox/archive/select.py",
          '    """보관 목록에서 쓰는 계정 이름."""\n    return account.strip().upper()',
          '    """보관 목록에서 쓰는 계정 이름. 입력 어댑터의 규칙을 그대로 쓴다."""\n'
          "    return normalize_account(account)")
    _edit(target / "opsbox/archive/select.py",
          "from ..record import is_billable",
          "from ..ingest.accounts import normalize_account\nfrom ..record import is_billable")
    _append_after(target / "docs/archive.md", "## 무엇을 골라 보관하나",
                  f"결정: {'크기' if pick == 'size' else '나이'}\n")
    _append_after(target / "docs/archive.md", "## 날짜 표기",
                  f"결정: {'빗금' if style == 'slash' else '붙임표'}\n")
    if pick == "size":
        _edit(target / "opsbox/cli.py",
              'picked = archive.by_age(records, as_of, settings["retain_days"])',
              "picked = archive.by_size(records, 100)")

    # ---------------------------------------------- E 내보내기
    if stable == "drop":
        _edit(target / "opsbox/export/flat.py",
              '    stamp = datetime.datetime.now().isoformat(timespec="seconds")\n'
              '    lines = [f"# generated {stamp}", ",".join(COLUMNS)]',
              '    lines = [",".join(COLUMNS)]')
    else:
        _edit(target / "opsbox/export/flat.py",
              "def to_csv(report: dict) -> str:",
              "def to_csv(report: dict, as_of: str = \"\") -> str:")
        _edit(target / "opsbox/export/flat.py",
              '    stamp = datetime.datetime.now().isoformat(timespec="seconds")\n'
              '    lines = [f"# generated {stamp}", ",".join(COLUMNS)]',
              '    lines = [f"# as_of {as_of}", ",".join(COLUMNS)]')
        _edit(target / "opsbox/cli.py", "text = export.to_csv(built)",
              'text = export.to_csv(built, settings["as_of"])')
    _append_after(target / "docs/export.md", "## 같은 입력이면 같은 바이트가 나와야 한다",
                  f"결정: {'기준일로 바꾼다' if stable == 'asof' else '시각 줄을 뺀다'}\n")

    # ---------------------------------------------- F 되채우기
    plan = target / "opsbox/backfill/plan.py"
    text = plan.read_text(encoding="utf-8")
    text = text.replace(
        "from .._internal.timeparse import to_utc\nfrom ..record import is_billable",
        "from ..ingest.accounts import normalize_account\n"
        "from ..record import is_billable\nfrom ..report.months import month_key")
    start = text.index("def _account(raw: str) -> str:")
    end = text.index("def published(")
    text = text[:start] + text[end:]
    text = text.replace("_account(record.account)", "normalize_account(record.account)")
    text = text.replace("_month_of(record)", "month_key(record)")
    plan.write_text(text, encoding="utf-8")

    # ---------------------------------------------- 저장소 전체
    # 설정 경고: 코드가 모르는 열쇠를 알게 한다.
    _edit(target / "opsbox/config.py",
          '    "max_alerts_per_day": 3,\n}',
          '    "max_alerts_per_day": 3,\n    "keep_originals": True,\n}')
    # 버전과 바뀐 것.
    _edit(target / "opsbox/__init__.py", '__version__ = "0.2.3"',
          '__version__ = "0.3.0"')
    _edit(target / "CHANGELOG.md", "# 바뀐 것\n",
          "# 바뀐 것\n\n## v0.3.0\n\n- 서브시스템 여섯의 결정을 서로 맞췄다.\n")
    # PDF 한 장.
    subprocess.run([sys.executable, "-c",
                    "import sys; sys.path.insert(0,'.');"
                    "from pathlib import Path;"
                    "from opsbox.ingest import read_all;"
                    "from opsbox.report import build;"
                    "from opsbox.export import pdf;"
                    "pdf.write('summary.pdf', build(read_all(Path('data'))))"],
                   cwd=target, check=True, capture_output=True)
    # 인계 문서. **"정한 것" 절은 덧붙이고 나머지만 새로 쓴다** — 과제가
    # 그렇게 요구하므로 레퍼런스 해답도 그렇게 해야 한다. 앞사람이 적어 둔
    # 결정을 지우면 다음다음 사람이 그것을 코드에서 찾아내야 한다.
    handoff = target / "HANDOFF.md"
    decided = "\n".join([
        f"- s01 계정 표기: {'대문자' if case == 'upper' else '소문자'}",
        f"- s01 달 경계: {'표준시' if basis == 'utc' else '현지 시각'}",
        f"- s01 날짜 표기: {'빗금' if style == 'slash' else '붙임표'}",
        f"- s01 알림 문턱 기준: "
        f"{'마지막 관측' if alert_basis == 'last' else '그 달 전체'}",
        f"- s01 보관 기준: {'크기' if pick == 'size' else '나이'}",
        f"- s01 내보내기 안정성: "
        f"{'기준일로 바꾼다' if stable == 'asof' else '시각 줄을 뺀다'}",
    ])
    text = handoff.read_text(encoding="utf-8")
    head, _, tail = text.partition("\n---\n")
    kept = head if tail else text
    handoff.write_text(
        kept.rstrip() + "\n" + decided + "\n\n---\n\n"
        "## 한 일\n\nv0.3 목록을 전부 처리했다.\n\n"
        "## 남은 일\n\n없다.\n\n"
        "## 다음 사람이 먼저 볼 것\n\n- `CHANGELOG.md`\n",
        encoding="utf-8")
    return target


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("target", type=Path)
    parser.add_argument("--other-way", action="store_true",
                        help="판단이 필요한 자리마다 반대쪽을 고른다")
    args = parser.parse_args()
    build(args.target, other_way=args.other_way)
    print(args.target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
