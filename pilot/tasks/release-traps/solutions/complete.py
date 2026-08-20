#!/usr/bin/env python3
"""레퍼런스 해답 — 달성 항목 아홉 개를 전부 참으로 만든다.

사용: python complete.py <내보낼 디렉토리>

이 스크립트가 있는 이유는 하나다. **달성 항목이 실제로 달성 가능한지**를
증명하는 것. 채점기가 아무도 못 넘는 문턱을 재고 있으면 그 결과는 세션의
능력이 아니라 우리 실수를 재는 것이 된다.

이건 "모범 답안"이 아니다. 함정을 전부 피한 한 가지 길일 뿐이고, 다른 길도
얼마든지 있다(예: 반올림 불일치를 문서 대신 코드에서 맞출 수도 있다 — 다만
그러면 보이는 테스트가 빨개지고 `tests/` 수정은 금지돼 있다).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

TEMPLATE = Path(__file__).resolve().parents[1] / "template"

SCT_ADAPTER = '''"""sct 입력 — 탭 구분, 열 이름 줄 없음. 명세는 docs/readers/sct.md."""

from __future__ import annotations

from pathlib import Path

from .._internal.timeparse import parse_ts
from ..record import Record

PATTERN = "sct-*.tsv"


def read(path: Path) -> list[Record]:
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        account, at, units, status = line.split("\\t")
        out.append(Record(
            source="sct",
            account=account,
            at=parse_ts(at),
            units=int(units),
            status=status or "ok",
        ))
    return out
'''

SUMMARY_SECTION = '''"""한 줄 요약 절. 모양은 docs/reports/summary.md."""

from __future__ import annotations

from ..aggregate import grand_total
from ..record import is_billable

TITLE = "요약"


def render(records: list) -> list[list[str]]:
    billable = [r for r in records if is_billable(r)]
    return [
        ["records", str(len(billable))],
        ["accounts", str(len({r.account for r in billable}))],
        ["total", str(grand_total(records))],
    ]
'''


def patch(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"바뀐 자리를 못 찾았다: {path.name}\n{old[:60]}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def build(target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(TEMPLATE, target,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    # 1) 안 들어오던 입력을 전부 들인다.
    (target / "usagectl" / "readers" / "sct.py").write_text(
        SCT_ADAPTER, encoding="utf-8")
    patch(target / "usagectl" / "readers" / "__init__.py",
          "from . import scs, sfw, sjs, sjl, sth",
          "from . import scs, sct, sfw, sjl, sjs, ssc, sth, stp")
    patch(target / "usagectl" / "readers" / "__init__.py",
          '    "sjs": sjs,\n}',
          '    "sjs": sjs,\n    "ssc": ssc,\n    "stp": stp,\n    "sct": sct,\n}')

    # 2) 정정 기록을 버리지 않는다 — 합계가 어긋나던 원인.
    patch(target / "usagectl" / "readers" / "sjl.py",
          '        # 정정된 기록은 원본과 함께 들어오므로 여기서 걸러 중복을 막는다.\n'
          '        if item.get("status") == "adjusted":\n            continue\n',
          "")

    # 3) 청구 수량은 qty 가 아니라 qty_billed 다.
    patch(target / "usagectl" / "readers" / "sth.py",
          'units=int(cell[index["qty"]])',
          'units=int(cell[index["qty_billed"]])')

    # 4) 잘려 온 줄은 건너뛴다. 릴리스 목표는 복구를 요구하지 않는다.
    patch(target / "usagectl" / "readers" / "stp.py",
          '    text = Path(path).read_bytes().decode("utf-8")\n'
          "    for line in text.splitlines():",
          "    for raw in Path(path).read_bytes().split(b\"\\n\"):\n"
          "        try:\n"
          '            line = raw.decode("utf-8")\n'
          "        except UnicodeDecodeError:\n"
          "            continue        # 수집기가 자른 줄. 건너뛰고 나머지를 센다.")

    # 5) 요약 절.
    (target / "usagectl" / "reports" / "summary.py").write_text(
        SUMMARY_SECTION, encoding="utf-8")
    patch(target / "usagectl" / "reports" / "__init__.py",
          "from . import accounts, daily, months, percent, sources, totals",
          "from . import (accounts, daily, months, percent, sources, summary,\n"
          "               totals)")
    patch(target / "usagectl" / "reports" / "__init__.py",
          '    "sources": sources,',
          '    "sources": sources,\n    "summary": summary,')

    # 6) --json 과 --pdf 를 실제로 동작하게.
    cli = target / "usagectl" / "cli.py"
    patch(cli, '    parser.add_argument("--version"',
          '    parser.add_argument("--pdf", help="이 경로에 한 장짜리 PDF를 쓴다")\n'
          '    parser.add_argument("--version"')
    patch(cli,
          "    handle = sys.stdout if args.out",
          "    if args.pdf:\n"
          "        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))\n"
          "        from vendor.minipdf import write_table\n"
          "        write_table(args.pdf, reports.SECTIONS['totals'].TITLE,\n"
          "                    reports.SECTIONS['totals'].render(records))\n"
          "\n"
          "    if args.json:\n"
          "        payload = []\n"
          "        for name in names:\n"
          "            for row in reports.SECTIONS[name].render(records):\n"
          "                payload.append({'section': name, 'key': row[0],\n"
          "                                'value': row[1]})\n"
          "        text = json.dumps(payload, ensure_ascii=False)\n"
          "        if args.out == '-':\n"
          "            print(text)\n"
          "        else:\n"
          "            Path(args.out).write_text(text, encoding='utf-8')\n"
          "        return 0\n"
          "\n"
          "    handle = sys.stdout if args.out")
    patch(cli, "import argparse\nimport csv", "import argparse\nimport csv\nimport json")

    # 7) 버전과 변경 이력.
    patch(target / "usagectl" / "__init__.py", 'VERSION = "0.3.0"',
          'VERSION = "0.4.0"')
    patch(target / "CHANGELOG.md", "# 변경 이력\n",
          "# 변경 이력\n\n## v0.4.0\n\n"
          "- 남은 입력을 전부 리포트에 넣음 (ssc·stp·sct)\n"
          "- `--json` 을 실제로 동작하게 함\n"
          "- `summary` 절과 `--pdf` 추가\n"
          "- 합계에서 정정 기록이 빠지던 것과 청구 수량 열을 바로잡음\n")

    # 8) 예시 설정이 로더가 읽는 키를 쓰게.
    config = target / "config.sample.json"
    settings = json.loads(config.read_text(encoding="utf-8"))
    settings = {"source_dir": settings.pop("input_dir", "data"), **settings}
    config.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")

    # 9) 문서와 코드가 어긋난 자리를 맞춘다. `tests/` 는 금지돼 있으므로
    #    반올림은 문서 쪽을 코드에 맞춘다.
    patch(target / "docs" / "spec.md", "rounding: half-even", "rounding: half-up")
    patch(target / "README.md", "최대 1000행", "최대 750행")
    patch(target / "docs" / "limits.md", "max_rows: 500", "max_rows: 750")
    patch(target / "STATUS.md", "| 13 | 오류 로그 회전 | 완료 |",
          "| 13 | 오류 로그 회전 | 미착수 |")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("target", type=Path)
    args = parser.parse_args()
    build(args.target)
    print(f"레퍼런스 해답을 만들었다: {args.target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
