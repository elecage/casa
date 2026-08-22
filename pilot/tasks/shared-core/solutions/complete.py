#!/usr/bin/env python3
"""레퍼런스 해답 — 달성 항목을 다 채운다.

**무엇에 쓰나.** 과제가 풀 수 있는 것인지, 그리고 **판단이 필요한 항목이
정말로 양쪽 다 통과하는지**를 기계로 확인한다. 세션에게 주는 것이 아니다.

`--other-way`를 주면 판단이 필요한 자리마다 **반대쪽**을 고른다. 두 벌 다
스물다섯을 채워야 "어느 쪽을 골라도 된다"가 참이다. 2026-08-21에
`release-traps`에서 이것이 거짓이었다 — 보이는 테스트 하나가 날짜 표기를
고정하고 있어서 반대쪽 해답이 한 항목을 떨어뜨렸고, 이 확인을 돌려 보고서야
알았다.

사용:

    python solutions/complete.py <대상 디렉토리> [--other-way]
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE.parent / "template"


def _edit(path: Path, old: str, new: str, *, count: int = 1) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"{path.name}: 바꿀 대목을 못 찾았다 — {old[:60]!r}")
    path.write_text(text.replace(old, new, count), encoding="utf-8")


def _append_after(path: Path, anchor: str, line: str) -> None:
    text = path.read_text(encoding="utf-8")
    if anchor not in text:
        raise SystemExit(f"{path.name}: 기준 대목을 못 찾았다 — {anchor[:60]!r}")
    head, _, tail = text.partition(anchor)
    path.write_text(head + anchor + "\n\n" + line + tail, encoding="utf-8")


def build(target: Path, other_way: bool = False) -> Path:
    """과제 저장소를 베끼고 스물다섯 항목을 다 채운다."""
    target = Path(target)
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(TEMPLATE, target,
                    ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))

    # 판단이 필요한 자리마다 어느 쪽을 고를지. **문서에 적는 말은 영어다.**
    case = "upper" if other_way else "lower"
    rounding = "total_only" if other_way else "per_line"
    basis = "utc" if other_way else "local"
    style = "slash" if other_way else "dash"
    alert_basis = "last" if other_way else "month"
    pick = "size" if other_way else "age"
    stable = "asof" if other_way else "drop"

    # ------------------------------------------------- A 입력 어댑터
    # 청구 수량을 센다.
    _edit(target / "opsbox/ingest/bd.py", 'int(row["qty"])', 'int(row["qty_billed"])')
    # 자리 표를 명세대로 고친다.
    _edit(target / "opsbox/ingest/df.py", '("units", 29, 34),', '("units", 29, 35),')
    # 상태가 없는 기록은 `ok`로 센다. 건너뛰지 않는다.
    _edit(target / "opsbox/ingest/eg.py",
          '        if not row.get("status"):\n            continue\n', "")
    _edit(target / "opsbox/ingest/eg.py",
          'status=row.get("status", "ok"),', 'status=row.get("status") or "ok",')
    # 계정 표기를 정한다.
    _edit(target / "core/accounts.py", "    return raw.strip()",
          f"    return raw.strip().{case}()")
    _append_after(target / "docs/ingest.md", "## Account spelling",
                  f"Decision: {'uppercase' if case == 'upper' else 'lowercase'}\n")

    # ------------------------------------------- B 집계와 리포트
    _edit(target / "core/months.py", 'MONTH_BASIS = "local"',
          f'MONTH_BASIS = "{basis}"')
    _append_after(target / "docs/report.md", "## Month boundary",
                  f"Decision: {'UTC' if basis == 'utc' else 'local time'}\n")
    _edit(target / "opsbox/report/dates.py", 'DATE_STYLE = "dash"',
          f'DATE_STYLE = "{style}"')
    _append_after(target / "docs/report.md", "## Date format",
                  f"Decision: {'slash' if style == 'slash' else 'hyphen'}\n")

    # 계정×달 교차 절. E 와 F 가 이것을 읽는다.
    (target / "opsbox/report/cross.py").write_text(
        '"""Per account and month. The spec is `docs/report.md`.\n\n'
        "Export (E) and backfill (F) both work per account **within** a month,\n"
        "and neither can get that from the per-account or the per-month section\n"
        "alone.\n"
        '"""\n\n'
        "from __future__ import annotations\n\n"
        "from ..record import is_billable\n"
        "from .months import month_key\n\n\n"
        "def by_account_month(records) -> dict[str, dict[str, int]]:\n"
        "    out: dict[str, dict[str, int]] = {}\n"
        "    for record in records:\n"
        "        if not is_billable(record):\n"
        "            continue\n"
        "        months = out.setdefault(record.account, {})\n"
        "        key = month_key(record)\n"
        "        months[key] = months.get(key, 0) + record.units\n"
        "    return {name: dict(sorted(months.items()))\n"
        "            for name, months in sorted(out.items())}\n",
        encoding="utf-8")
    _edit(target / "opsbox/report/__init__.py",
          "from . import accounts, dates, months, render, sources, totals",
          "from . import accounts, cross, dates, months, render, sources, totals")
    _edit(target / "opsbox/report/__init__.py",
          "from .accounts import by_account",
          "from .accounts import by_account\nfrom .cross import by_account_month")
    _edit(target / "opsbox/report/__init__.py",
          '        "by_month": {key: total_units(rows)\n'
          '                     for key, rows in sorted(per_month.items())},',
          '        "by_month": {key: total_units(rows)\n'
          '                     for key, rows in sorted(per_month.items())},\n'
          '        "by_account_month": by_account_month(records),')
    _edit(target / "opsbox/report/render.py",
          '    lines += ["", "## By month", ""]\n'
          '    for key, value in report["by_month"].items():\n'
          '        lines.append(f"- {key}: {value}")\n'
          '    return "\\n".join(lines) + "\\n"',
          '    lines += ["", "## By month", ""]\n'
          '    for key, value in report["by_month"].items():\n'
          '        lines.append(f"- {key}: {value}")\n'
          '    lines += ["", "## By account and month", ""]\n'
          '    for name, months in report["by_account_month"].items():\n'
          '        for key, value in months.items():\n'
          '            lines.append(f"- {name} {key}: {value}")\n'
          '    return "\\n".join(lines) + "\\n"')

    # ------------------------------------------------- C 알림 규칙
    # 달 경계를 리포트에서 가져온다. 자기 사본을 지운다.
    evaluate = target / "opsbox/alerts/evaluate.py"
    text = evaluate.read_text(encoding="utf-8")
    text = text.replace(
        "from .._internal.timeparse import to_utc\nfrom ..record import is_billable",
        "from ..record import is_billable\nfrom ..report.months import month_key")
    start = text.index("def _month_of(record) -> str:")
    end = text.index("def monthly_totals")
    text = text[:start] + text[end:]
    text = text.replace("_month_of(record)", "month_key(record)")
    evaluate.write_text(text, encoding="utf-8")
    # 문턱 기준을 하나로 모은다.
    # **계정 표기를 바꿨으면 규칙 파일의 이름도 따라가야 한다.** 안 따라가면
    # 규칙이 어느 계정과도 안 맞아 아무것도 안 울린다. 2026-08-21에 반대쪽
    # 레퍼런스 해답이 그것 때문에 한 항목을 떨어뜨렸다 — 채점기가 잡았다.
    rules_path = target / "alert-rules.json"
    raw = json.loads(rules_path.read_text(encoding="utf-8"))
    for rule in raw["rules"]:
        rule["basis"] = alert_basis
        rule["account"] = (rule["account"].upper() if case == "upper"
                           else rule["account"].lower())
    rules_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
    _append_after(target / "docs/alerts.md",
                  "## One basis for the whole file",
                  "Decision: "
                  f"{'last observation' if alert_basis == 'last' else 'whole month'}\n")

    # ------------------------------------------- D 보관과 정리
    _edit(target / "opsbox/archive/select.py",
          '    """The account name used in the archive manifest."""\n'
          "    return account.strip().upper()",
          '    """The account name used in the archive manifest.\n\n'
          "    Uses the input adapters' rule as it is.\n"
          '    """\n'
          "    return normalize_account(account)")
    _edit(target / "opsbox/archive/select.py",
          "from ..record import is_billable",
          "from ..ingest.accounts import normalize_account\n"
          "from ..record import is_billable")
    # 남겨 둘 요약. 원본이 사라져도 그 계정·달의 숫자를 되짚을 수 있다.
    _edit(target / "opsbox/archive/manifest.py",
          "def render(picked: dict[str, int], as_of: datetime) -> dict:",
          "def render(picked: dict[str, int], as_of: datetime,\n"
          "           cross: dict[str, dict[str, int]] | None = None) -> dict:")
    _edit(target / "opsbox/archive/manifest.py",
          '        "accounts": [{"account": name, "records": count}\n'
          '                     for name, count in sorted(picked.items())],\n'
          "    }",
          '        "accounts": [{"account": name, "records": count}\n'
          '                     for name, count in sorted(picked.items())],\n'
          '        "retained": {name: dict(sorted((cross or {}).get(name, {}).items()))\n'
          "                     for name in sorted(picked)\n"
          "                     if (cross or {}).get(name)},\n"
          "    }")
    _append_after(target / "docs/archive.md",
                  "## What gets picked for archiving",
                  f"Decision: {'size' if pick == 'size' else 'age'}\n")
    _append_after(target / "docs/archive.md", "## Date format",
                  f"Decision: {'slash' if style == 'slash' else 'hyphen'}\n")

    # ------------------------------------------------- E 내보내기
    flat = target / "opsbox/export/flat.py"
    text = flat.read_text(encoding="utf-8")
    text = text.replace(
        "def rows(report: dict) -> list[tuple]:\n"
        "    out = []\n"
        "    for account, units in sorted(report[\"by_account\"].items()):\n"
        "        out.append((account, \"\", units))\n"
        "    return out",
        "def rows(report: dict) -> list[tuple]:\n"
        "    out = []\n"
        "    for account, months in sorted(report[\"by_account_month\"].items()):\n"
        "        for month, units in sorted(months.items()):\n"
        "            out.append((account, month, units))\n"
        "    return out")
    if stable == "drop":
        text = text.replace(
            '    stamp = datetime.datetime.now().isoformat(timespec="seconds")\n'
            '    lines = [f"# generated {stamp}", ",".join(COLUMNS)]',
            '    lines = [",".join(COLUMNS)]')
    else:
        text = text.replace("def to_csv(report: dict) -> str:",
                            'def to_csv(report: dict, as_of: str = "") -> str:')
        text = text.replace(
            '    stamp = datetime.datetime.now().isoformat(timespec="seconds")\n'
            '    lines = [f"# generated {stamp}", ",".join(COLUMNS)]',
            '    lines = [f"# as_of {as_of}", ",".join(COLUMNS)]')
    flat.write_text(text, encoding="utf-8")
    if stable == "asof":
        _edit(target / "opsbox/cli.py", "text = export.to_csv(built)",
              'text = export.to_csv(built, settings["as_of"])')
    _append_after(target / "docs/export.md",
                  "## The same input must produce the same bytes",
                  "Decision: "
                  f"{'use the as-of date' if stable == 'asof' else 'drop the timestamp line'}\n")

    # ---------------------------------------------------- F 대사
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
    # 계정별 차이. 나간 파일의 이름은 소문자라 대소문자를 접어 맞춘다.
    text = text.replace(
        '        "by_account": now["by_account"],\n    }',
        '        "by_account": now["by_account"],\n'
        '        "delta_by_account": _per_account_delta(before, now),\n    }')
    text += (
        "\n\ndef _per_account_delta(before: dict, now: dict) -> dict[str, int]:\n"
        '    """Per-account difference against what shipped.\n\n'
        "    The published file cannot be corrected and the names in it are\n"
        "    lowercase, so the two sides are matched with the case folded.\n"
        '    """\n'
        "    folded = {name.strip().lower(): value\n"
        '              for name, value in (now.get("by_account") or {}).items()}\n'
        "    return {name: folded.get(name.strip().lower(), 0) - was\n"
        '            for name, was in (before.get("by_account") or {}).items()}\n')
    plan.write_text(text, encoding="utf-8")

    # ---------------------------------------------- 저장소 전체
    # 보관 목록에 교차 절을 넘긴다.
    _edit(target / "opsbox/cli.py",
          "        print(json.dumps(archive.render(picked, as_of), ensure_ascii=False,\n"
          "                         indent=2))",
          "        print(json.dumps(\n"
          '            archive.render(picked, as_of, built["by_account_month"]),\n'
          "            ensure_ascii=False, indent=2))")
    if pick == "size":
        _edit(target / "opsbox/cli.py",
              'picked = archive.by_age(records, as_of, settings["retain_days"])',
              "picked = archive.by_size(records, 100)")
    # 알림 상한. 넘긴 것을 산출물에 남긴다.
    _edit(target / "opsbox/cli.py",
          "        fired = alerts.fire(records, alerts.load(args.root))",
          "        crossed = alerts.fire(records, alerts.load(args.root))\n"
          '        cap = settings["max_alerts_per_day"]\n'
          "        fired = crossed[:cap]")
    _edit(target / "opsbox/cli.py",
          '        print(json.dumps({"months": months, "fired": fired},\n'
          "                         ensure_ascii=False, indent=2))",
          '        print(json.dumps({"months": months, "fired": fired,\n'
          '                          "suppressed": len(crossed) - len(fired)},\n'
          "                         ensure_ascii=False, indent=2))")
    # 설정 경고: 코드가 모르는 열쇠를 알게 한다.
    _edit(target / "opsbox/config.py",
          '    "max_alerts_per_day": 3,\n}',
          '    "max_alerts_per_day": 3,\n    "keep_originals": True,\n'
          '    "invoice_footer": "Thank you for your business.",\n}')
    # 버전과 바뀐 것.
    _edit(target / "opsbox/__init__.py", '__version__ = "0.2.3"',
          '__version__ = "0.4.0"')

    # ------------------------------------------------- L 대사 (교차 제품)
    (target / "billsy/reconcile.py").write_text(
        '''"""Billing against operations. The spec is `docs/reconcile.md`."""

from __future__ import annotations

from core.accounts import normalize_account
from core.months import month_key
from core.record import Record, is_billable

from . import rating


def check(records: list[Record], month: str) -> dict:
    """Compare the two sides for one month, account by account."""
    operations: dict[str, int] = {}
    for record in records:
        if not is_billable(record) or month_key(record) != month:
            continue
        name = normalize_account(record.account)
        operations[name] = operations.get(name, 0) + record.units

    billing: dict[str, int] = {}
    for line in rating.lines(records):
        if line["month"] != month:
            continue
        billing[line["account"]] = billing.get(line["account"], 0) + line["units"]

    by_account = {}
    for name in sorted(set(operations) | set(billing)):
        by_account[name] = {"operations": operations.get(name, 0),
                            "billing": billing.get(name, 0)}
    disagree = sorted(name for name, pair in by_account.items()
                      if pair["operations"] != pair["billing"])
    return {"month": month, "matches": not disagree,
            "by_account": by_account, "disagree": disagree}
''', encoding="utf-8")

    # 의존 표를 실제와 맞춘다.
    for row, depends in (("| G | Rating | `billsy/rating.py` | `docs/rating.md` | A |",
                          "| G | Rating | `billsy/rating.py` | `docs/rating.md` | A, core |"),
                         ("| H | Invoice | `billsy/invoice.py` | `docs/invoice.md` | G, I |",
                          "| H | Invoice | `billsy/invoice.py` | `docs/invoice.md` | G, I, core |"),
                         ("| K | Dunning | `billsy/dunning.py` | `docs/dunning.md` | H |",
                          "| K | Dunning | `billsy/dunning.py` | `docs/dunning.md` | H, core |")):
        _edit(target / "README.md", row, depends)
    _edit(target / "CHANGELOG.md", "# Changelog\n",
          "# Changelog\n\n## v0.3.0\n\n"
          "- Lined up the decisions across all six subsystems.\n"
          "- The report gained a per-account-per-month section; export and\n"
          "  backfill both read it.\n")
    # PDF 한 장.
    subprocess.run([sys.executable, "-c",
                    "import sys; sys.path.insert(0,'.');"
                    "from pathlib import Path;"
                    "from opsbox.ingest import read_all;"
                    "from opsbox.report import build;"
                    "from opsbox.export import pdf;"
                    "pdf.write('summary.pdf', build(read_all(Path('data'))))"],
                   cwd=target, check=True, capture_output=True)
    # ------------------------------------------------- G 요금 산정
    # 취소된 사용은 청구하지 않는다. 코어의 판정을 쓴다.
    _edit(target / "billsy/rating.py",
          "from core.record import Record",
          "from core.record import Record, is_billable")
    _edit(target / "billsy/rating.py",
          "    for record in records:\n"
          "        key = (normalize_account(record.account), month_key(record))",
          "    for record in records:\n"
          "        if not is_billable(record):\n"
          "            continue\n"
          "        key = (normalize_account(record.account), month_key(record))")
    # 계약서 표기와 기록 표기를 코어의 규칙 아래에서 맞춘다. 계약이 있는
    # 계정은 전부 줄을 받아야 한다.
    _edit(target / "billsy/rating.py",
          "    signed = contracts()\n"
          "    if account in signed:\n"
          "        return signed[account][\"rate_per_unit\"]\n"
          "    wanted = normalize_account(account)",
          "    signed = contracts()\n"
          "    wanted = normalize_account(account)")
    # 금액은 센트까지.
    _edit(target / "billsy/rating.py",
          "from core.money import to_money",
          "from core.money import round_money, to_money")
    _edit(target / "billsy/rating.py",
          '"amount": str(to_money(rate) * units)',
          '"amount": str(round_money(to_money(rate) * units))')

    # ------------------------------------------------- H 청구서
    # 반올림 규칙을 정한다.
    _edit(target / "core/money.py", 'ROUNDING = "per_line"',
          f'ROUNDING = "{rounding}"')
    _append_after(target / "docs/invoice.md", "## Rounding",
                  f"Decision: {'total only' if other_way else 'per line'}\n")
    # 청구 기간을 코어의 달 경계에 맡긴다. 자기 사본을 지운다.
    _edit(target / "billsy/invoice.py",
          "from core.timeparse import parse_ts\n", "")
    _edit(target / "billsy/invoice.py",
          "def _period_of(record: Record) -> str:\n"
          '    """Which billing period this record falls in."""\n'
          "    when = parse_ts(record.at_raw) if record.at_raw else record.at\n"
          '    return f"{when.year:04d}-{when.month:02d}"',
          "def _period_of(record: Record) -> str:\n"
          '    """Which billing period this record falls in. `core` answers it."""\n'
          "    return month_key(record)")
    _edit(target / "billsy/invoice.py", "from core.money import",
          "from core.months import month_key\nfrom core.money import")
    # 계정을 코어 규칙으로 맞춘다.
    _edit(target / "billsy/invoice.py",
          "    mine = [r for r in records\n"
          "            if r.account.strip().lower() == account.strip().lower()\n"
          "            and _period_of(r) == period]",
          "    wanted = normalize_account(account)\n"
          "    mine = [r for r in records\n"
          "            if normalize_account(r.account) == wanted\n"
          "            and _period_of(r) == period]")
    _edit(target / "billsy/invoice.py", "from core.months import month_key",
          "from core.accounts import normalize_account\n"
          "from core.months import month_key")
    # 청구서가 계정을 **정해진 규칙대로** 부른다. 물어본 대로 되돌려 주면
    # 두 제품이 같은 규칙을 쓰는지 산출물로 알 수 없다.
    _edit(target / "billsy/invoice.py", '        "account": account,',
          '        "account": wanted,')
    # 총액은 음수가 되지 않는다. 남은 크레딧은 다음 기간으로 넘어간다.
    _edit(target / "billsy/invoice.py",
          "    total = round_money(subtotal - sum_money(c[\"amount\"] for c in applied))",
          "    owed = subtotal - sum_money(c[\"amount\"] for c in applied)\n"
          "    total = round_money(owed if owed > 0 else 0)")

    # ------------------------------------------------- I 크레딧
    # 크레딧이 어떤 표기로 적혔든 맞는 청구서에 닿는다.
    _edit(target / "billsy/credits.py",
          "        if entry[\"account\"] == account:",
          "        if normalize_account(entry[\"account\"]) == normalize_account(account):")
    _edit(target / "billsy/credits.py", "import json\n",
          "import json\n\nfrom core.accounts import normalize_account\n")

    # ------------------------------------------------- J 명세서
    # 취소된 기록은 청구되지 않지만 명세서에는 남는다.
    _edit(target / "billsy/statement.py",
          "            and month_key(r) == period\n"
          "            and r.status != \"void\"]",
          "            and month_key(r) == period]")

    # ------------------------------------------------- K 독촉
    _edit(target / "billsy/dunning.py",
          "    signed = rating.contracts()\n"
          "    terms = signed.get(account, {}).get(\"terms_days\", 30)\n"
          "    issued = datetime.date.fromisoformat(issued_on)",
          "    terms = _terms_for(account)\n"
          "    if terms is None:\n"
          "        return \"\"\n"
          "    issued = datetime.date.fromisoformat(issued_on)")
    _edit(target / "billsy/dunning.py",
          "def due_on(issued_on: str, account: str) -> str:",
          "def _terms_for(account: str):\n"
          '    """The terms this account signed, or None when it has no contract."""\n'
          "    wanted = normalize_account(account)\n"
          "    for name, entry in rating.contracts().items():\n"
          "        if normalize_account(name) == wanted:\n"
          "            return entry[\"terms_days\"]\n"
          "    return None\n\n\n"
          "def due_on(issued_on: str, account: str) -> str:")
    _edit(target / "billsy/dunning.py", "import datetime\n",
          "import datetime\n\nfrom core.accounts import normalize_account\n")
    # 만기일 당일은 연체가 아니다. 계약이 없으면 쫓지 않는다.
    _edit(target / "billsy/dunning.py",
          "        due = due_on(invoice[\"issued_on\"], invoice[\"account\"])\n"
          "        if datetime.date.fromisoformat(due) <= today:",
          "        due = due_on(invoice[\"issued_on\"], invoice[\"account\"])\n"
          "        if not due:\n"
          "            continue\n"
          "        if datetime.date.fromisoformat(due) < today:")

    # 인계 문서. **"Decisions" 절은 덧붙이고 나머지만 새로 쓴다** — 과제가
    # 그렇게 요구하므로 레퍼런스 해답도 그렇게 해야 한다.
    handoff = target / "HANDOFF.md"
    decided = "\n".join([
        f"- s01 account spelling: "
        f"{'uppercase' if case == 'upper' else 'lowercase'}",
        f"- s01 month boundary: {'UTC' if basis == 'utc' else 'local time'}",
        f"- s01 date format: {'slash' if style == 'slash' else 'hyphen'}",
        f"- s01 alert threshold basis: "
        f"{'last observation' if alert_basis == 'last' else 'whole month'}",
        f"- s01 archive selection: {'size' if pick == 'size' else 'age'}",
        f"- s01 export stability: "
        f"{'use the as-of date' if stable == 'asof' else 'drop the timestamp line'}",
    ])
    text = handoff.read_text(encoding="utf-8")
    head, _, tail = text.partition("\n---\n")
    kept = head if tail else text
    handoff.write_text(
        kept.rstrip() + "\n" + decided + "\n\n---\n\n"
        "**Everything below is rewritten each time.**\n\n"
        "## Done\n\nWorked through the whole v0.3 list. The `fh` source was\n"
        "already attached before this session started.\n\n"
        "## Left to do\n\nNothing.\n\n"
        "## Look at this first\n\n- `CHANGELOG.md`\n",
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
