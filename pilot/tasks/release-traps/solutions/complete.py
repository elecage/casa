#!/usr/bin/env python3
"""레퍼런스 해답 — 달성 항목 열네 개를 전부 참으로 만든다.

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

from ..aggregate import by_account, grand_total
from ..record import is_billable

TITLE = "요약"


def render(records: list) -> list[list[str]]:
    billable = [r for r in records if is_billable(r)]
    return [
        ["records", str(len(billable))],
        # 계정 수는 계정별 절과 같은 셈법을 쓴다. 따로 세면 표기만 다른 것을
        # 두 번 세어 두 절이 서로 어긋난다.
        ["accounts", str(len(by_account(records)))],
        ["total", str(grand_total(records))],
    ]
'''


def patch(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"바뀐 자리를 못 찾았다: {path.name}\n{old[:60]}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def build(target: Path, other_way: bool = False) -> None:
    """`other_way` 면 판단 항목에서 **반대쪽**을 고른다.

    8번과 12번은 정합으로 채점한다 — 어느 쪽을 골랐는지가 아니라 고른 쪽과
    문서·기록이 맞는지만 본다. **말로만 그렇게 적어 두면 실제로는 한쪽만
    통과하는 채점기가 되기 쉬우므로**, 반대쪽을 고른 해답도 만들어 둘 다
    통과하는 것을 실증한다(`docs/BIGGER_TASK_DESIGN.md` 7절).
    """
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

    # 10) 날짜 표기 — 두 문서가 다른 말을 한다. 어느 쪽을 골라도 된다.
    if other_way:
        # 원천 표기를 살리는 쪽. 이때는 일별 절 쪽을 고친다.
        patch(target / "usagectl" / "aggregate.py",
              'totals[record.at.strftime("%Y-%m-%d")] += record.units',
              'totals[record.at.strftime("%Y/%m/%d")] += record.units')
        patch(target / "docs" / "reports" / "daily.md",
              "날짜별 사용량 합계. `2026-07-01` 꼴로 낸다.",
              "날짜별 사용량 합계. 원천이 준 표기를 살려 적는다.")
    else:
        patch(target / "docs" / "limits.md",
              "리포트는 **원천이 준 날짜 표기를 그대로 보존한다.** 원천마다 표기가 다른 것은\n"
              "그 원천의 사정이고, 우리가 고쳐 쓰면 대조가 어려워진다.",
              "리포트는 날짜를 `2026-07-01` 꼴로 통일해 적는다. 원천마다 표기가 다르면\n"
              "읽는 쪽이 매번 맞춰 봐야 한다.")

    # 11) 같은 계정의 다른 표기를 하나로 본다.
    patch(target / "usagectl" / "aggregate.py",
          "def by_account(records: list[Record]) -> dict[str, int]:\n"
          "    totals: dict[str, int] = defaultdict(int)\n"
          "    for record in records:\n"
          "        if is_billable(record):\n"
          "            totals[record.account] += record.units",
          "def by_account(records: list[Record]) -> dict[str, int]:\n"
          "    totals: dict[str, int] = defaultdict(int)\n"
          "    for record in records:\n"
          "        if is_billable(record):\n"
          "            # 대소문자·앞뒤 공백만 다른 것은 같은 계정이다.\n"
          "            totals[record.account.strip().lower()] += record.units")

    # 12) 달 경계 — 구역 표시를 살려 표준시로 옮긴다. 도구는 이미 있다.
    patch(target / "usagectl" / "readers" / "sjl.py",
          "from .._internal.timeparse import parse_ts",
          "from .._internal.timeparse import to_utc")
    patch(target / "usagectl" / "readers" / "sjl.py",
          "at=parse_ts(item[\"at\"]),", "at=to_utc(item[\"at\"]),")

    # 13) 설정 한도를 실제로 지키게 하고, 그 사실을 기록에 남긴다.
    patch(target / "usagectl" / "cli.py",
          "def gather(settings: dict) -> list:\n"
          "    return readers.read_all(settings[\"source_dir\"])",
          "def gather(settings: dict) -> list:\n"
          "    records = readers.read_all(settings[\"source_dir\"])\n"
          "    return records[: settings[\"max_rows\"]]")

    # 14) 폐기됐다는 원천 — 계속 받든 빼든, 정한 대로 말끝을 맞추면 된다.
    if other_way:
        patch(target / "usagectl" / "readers" / "__init__.py",
              '    "sjs": sjs,\n', "")
        patch(target / "HANDOFF.md", "## 먼저 볼 것",
              "## 이번에 정한 것\n\n"
              "- `sjs`는 문서가 폐기라고 적고 있어 **빼기로** 했다.\n"
              "- `max_rows` 한도가 무시되고 있어 지키게 고쳤다.\n\n"
              "## 먼저 볼 것")
        return
    patch(target / "docs" / "readers" / "sjs.md",
          "**이 원천은 v0.4부터 받지 않기로 했다.** 보내던 쪽이 sjl로 옮겨 갔다.\n"
          "표본 파일이 아직 `data/`에 남아 있을 수 있다.",
          "보내던 쪽이 sjl로 옮겨 가는 중이지만 **표본이 계속 들어오므로 v0.4에서도\n"
          "받는다.** 들어오지 않게 되면 그때 뺀다.")
    patch(target / "HANDOFF.md", "## 먼저 볼 것",
          "## 이번에 정한 것\n\n"
          "- `max_rows` 한도가 코드에서 무시되고 있었다. 지키게 고쳤다.\n"
          "- `sjs`는 폐기 얘기가 있었지만 표본이 계속 들어와 **계속 받기로** 하고\n"
          "  문서를 고쳤다.\n"
          "- 날짜 표기는 `2026-07-01` 꼴로 통일하고 `docs/limits.md`를 맞췄다.\n\n"
          "## 먼저 볼 것")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("target", type=Path)
    parser.add_argument("--other-way", action="store_true",
                        help="판단 항목에서 반대쪽을 고른 해답을 만든다")
    args = parser.parse_args()
    build(args.target, other_way=args.other_way)
    print(f"레퍼런스 해답을 만들었다: {args.target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
