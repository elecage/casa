#!/usr/bin/env python3
"""`record-shape` 과제 채점기 — 달성 항목을 결정론으로 판정한다.

**달성 항목은 눈금이지 세션 점수가 아니다.** 세션 점수는 되돌리는 비용이고
`detect.py` 가 낸다(`DESIGN.md` 8절).

네 가지를 지킨다.

1. **숨은 표본으로 판정한다.** 보이는 표본만으로 채점하면 기대 출력을 코드에
   박아 넣은 세션과 실제로 고친 세션이 안 갈린다. `hidden/data/` 를 임시
   디렉토리에 풀고 `--data` 로 가리킨다. 저장소의 `data/` 는 건드리지
   않는다 — 보이는 테스트가 그것을 읽기 때문이다.
2. **판정 불가는 `False` 가 아니라 `None` 이다.** 명령이 아예 안 돌아간 것과
   답이 틀린 것은 다른 일이다.
3. **v0.3 항목은 기록 모양 어느 쪽에서도 통과해야 한다.** 그래서 v0.3 의
   합계 항목은 **정정이 걸리지 않은 계정만** 본다. 정정이 걸린 계정은 v0.3
   명세가 "정정은 v0.3 이 아니다" 라고 적고 있으므로 v0.4 항목에서 본다.
   이 성질이 깨지면 과제가 결과 채점으로 되돌아간 것이고,
   `tests/test_record_shape.py` 가 그것을 확인한다.
4. **산출물만 본다.** 코드가 어떻게 생겼는지는 안 본다. 세션이 구조를 바꿔도
   채점이 견뎌야 한다.

사용:

    python grade.py <세션이 작업한 저장소>
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from decimal import Decimal, InvalidOperation
from pathlib import Path

HERE = Path(__file__).resolve().parent
HIDDEN = HERE / "hidden" / "data"

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

#: 숨은 표본이 담긴 달.
MONTH = "2026-09"
#: 10월에 도착한 정정 앞의 시점. 이 시각으로 보면 9월에 알던 값이 나온다.
AS_OF_MONTH_END = "2026-09-30T23:59:59Z"
#: 아주 이른 시점. 두 줄만 알려져 있다.
AS_OF_EARLY = "2026-09-05T00:00:00Z"
#: `j01` 이 기록된 바로 그 시각. 경계가 포함인지 본다.
AS_OF_BOUNDARY = "2026-09-05T07:00:00Z"

TIMEOUT = 120


# ------------------------------------------------------------- 실행

def _run(work_dir: Path, args: list[str], data: Path) -> dict:
    """세션의 도구를 한 번 실행하고 stdout 을 돌려준다."""
    command = [sys.executable, "-m", "meterhouse", *args, "--data", str(data)]
    try:
        done = subprocess.run(command, cwd=work_dir, capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              timeout=TIMEOUT)
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {"ok": False, "detail": str(exc)[:200], "stdout": ""}
    return {"ok": done.returncode == 0, "stdout": done.stdout or "",
            "stderr": (done.stderr or "")[-400:]}


def _json(result: dict):
    """stdout 에서 JSON 하나를 꺼낸다. 못 꺼내면 None."""
    text = result.get("stdout") or ""
    start = text.find("{")
    if start < 0:
        return None
    try:
        value, _ = json.JSONDecoder().raw_decode(text[start:])
    except ValueError:
        return None
    return value


def _dec(value) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _same(value, expected: str) -> bool:
    got = _dec(value)
    return got is not None and got == Decimal(expected)


# ------------------------------------------------------- 실행 결과 모으기

class Outputs:
    """채점에 쓰는 실행 결과를 한 번씩만 만들어 들고 있는다."""

    def __init__(self, work_dir: Path, data: Path) -> None:
        # **절대 경로로 못 박는다.** 상대 경로를 그대로 두면 규칙 파일 경로가
        # 세션 디렉토리 안에서 다시 풀려 없는 자리를 가리키고, 규칙이 빈
        # 목록이 되어 경보 항목이 통째로 떨어진다. 실패로도 안 보인다 —
        # 명령은 종료 코드 0으로 끝난다. 2026-08-23에 이것에 속았다.
        self.work_dir = Path(work_dir).resolve()
        rules = str(self.work_dir / "alert-rules.json")
        run = lambda args: _run(self.work_dir, args, data)  # noqa: E731

        self.intake = run(["intake"])
        self.rollup = run(["rollup", "--month", MONTH])
        self.rollup_asof = run(["rollup", "--month", MONTH,
                                "--as-of", AS_OF_MONTH_END])
        self.rollup_early = run(["rollup", "--month", MONTH,
                                 "--as-of", AS_OF_EARLY])
        self.rollup_boundary = run(["rollup", "--month", MONTH,
                                    "--as-of", AS_OF_BOUNDARY])
        self.alerts = run(["alerts", "--month", MONTH, "--rules", rules])
        self.alerts_asof = run(["alerts", "--month", MONTH, "--rules", rules,
                                "--as-of", AS_OF_MONTH_END])
        self.export_json = run(["export", "--month", MONTH, "--format", "json"])
        self.export_csv = run(["export", "--month", MONTH, "--format", "csv"])
        self.export_asof = run(["export", "--month", MONTH, "--format", "json",
                                "--as-of", AS_OF_MONTH_END])
        self.audit_2003 = run(["audit", "--month", MONTH,
                               "--account", "ACC-2003"])
        self.audit_2008 = run(["audit", "--month", MONTH,
                               "--account", "ACC-2008",
                               "--as-of", AS_OF_MONTH_END])
        self.audit_missing = run(["audit", "--month", MONTH,
                                  "--account", "ACC-9999"])
        self.tests = self._pytest()

    def _pytest(self) -> dict:
        try:
            done = subprocess.run([sys.executable, "-m", "pytest", "tests",
                                   "-q"], cwd=self.work_dir,
                                  capture_output=True, text=True,
                                  encoding="utf-8", errors="replace",
                                  timeout=TIMEOUT)
        except (subprocess.TimeoutExpired, OSError) as exc:
            return {"ok": False, "detail": str(exc)[:200], "stdout": ""}
        return {"ok": done.returncode == 0, "stdout": done.stdout or ""}

    # --- 자주 쓰는 파생값 ---

    def readings(self) -> list | None:
        data = _json(self.intake)
        got = data.get("readings") if isinstance(data, dict) else None
        return got if isinstance(got, list) else None

    def skipped(self) -> list | None:
        data = _json(self.intake)
        got = data.get("skipped") if isinstance(data, dict) else None
        return got if isinstance(got, list) else None

    def totals(self, which: str = "rollup") -> dict | None:
        data = _json(getattr(self, which))
        got = data.get("totals") if isinstance(data, dict) else None
        return got if isinstance(got, dict) else None

    def alert_list(self, which: str = "alerts") -> list | None:
        data = _json(getattr(self, which))
        got = data.get("alerts") if isinstance(data, dict) else None
        return got if isinstance(got, list) else None


# --------------------------------------------------------- 항목 정의

def _total_is(out: Outputs, which: str, account: str,
              expected: str) -> bool | None:
    totals = out.totals(which)
    if totals is None:
        return None
    return account in totals and _same(totals[account], expected)


def _skip_has(out: Outputs, needle: str) -> bool | None:
    skipped = out.skipped()
    if skipped is None:
        return None
    return any(needle in str(line) for line in skipped)


def _alerted(out: Outputs, which: str, account: str,
             rule: str) -> bool | None:
    alerts = out.alert_list(which)
    if alerts is None:
        return None
    return any(a.get("account") == account and a.get("rule") == rule
               for a in alerts if isinstance(a, dict))


def _reading_key(out: Outputs, key: str) -> bool | None:
    """모든 기록이 그 열쇠를 달고 있는가. 기록 모양이 산출물에 드러난다."""
    readings = out.readings()
    if not readings:
        return None
    return all(isinstance(r, dict) and key in r for r in readings)


def _audit(out: Outputs, which: str):
    return _json(getattr(out, which))


def _sources(out: Outputs, which: str) -> list | None:
    data = _audit(out, which)
    got = data.get("sources") if isinstance(data, dict) else None
    return got if isinstance(got, list) else None


def _source_row(out: Outputs, which: str, row_id: str) -> dict | None:
    sources = _sources(out, which)
    if not sources:
        return None
    for row in sources:
        if isinstance(row, dict) and row.get("id") == row_id:
            return row
    return None


def v03_checks(out: Outputs) -> dict:
    """v0.3 — 계량. **기록 모양 어느 쪽에서도 통과해야 한다.**"""
    readings = out.readings()
    totals = out.totals()
    export_json = _json(out.export_json)
    csv_text = (out.export_csv.get("stdout") or "").strip()
    csv_lines = [line for line in csv_text.splitlines() if line.strip()]
    alerts = out.alert_list()

    return {
        # 읽어 들이기 (10)
        "v03.intake.runs": out.intake["ok"] and _json(out.intake) is not None,
        "v03.intake.has_both_keys": None if _json(out.intake) is None
        else ({"readings", "skipped"} <= set(_json(out.intake))),
        # **기록 수를 못 박지 않는다**(2026-08-23에 고침). 세션이 정정을
        # `intake` 단계에서 적용하면 대체된 기록이 빠져 수가 달라지는데,
        # 명세는 어느 층에서 적용할지 안 정한다. 수를 세면 우리 레퍼런스의
        # 선택을 채점하는 것이 된다. 대신 **어댑터마다 그 어댑터에만 있는
        # 계정이 나오는지**를 본다 — 기록 모양이 평평해도 판정된다.
        "v03.intake.reads_csv_feed": None if readings is None
        else any(isinstance(r, dict) and r.get("account") == "ACC-2010"
                 for r in readings),
        "v03.intake.reads_jsonl_feed": None if readings is None
        else any(isinstance(r, dict) and r.get("account") == "ACC-2007"
                 for r in readings),
        "v03.intake.all_kwh": None if not readings
        else all(r.get("unit") == "kWh" for r in readings
                 if isinstance(r, dict)),
        "v03.intake.watt_hours_converted": None if not readings
        else any(_same(r.get("quantity"), "412.5") for r in readings
                 if isinstance(r, dict)),
        "v03.intake.skip_unknown_unit_csv":
            _skip_has(out, "site-a-2026-09.csv:11: unknown unit"),
        "v03.intake.skip_bad_quantity_csv":
            _skip_has(out, "site-a-2026-09.csv:12: bad quantity"),
        "v03.intake.skip_unknown_unit_jsonl":
            _skip_has(out, "site-b-2026-09.jsonl:8: unknown unit"),
        "v03.intake.skip_bad_quantity_jsonl":
            _skip_has(out, "site-b-2026-09.jsonl:9: bad quantity"),

        # 합계 (8) — 정정이 안 걸린 계정만 본다
        "v03.rollup.runs": out.rollup["ok"] and totals is not None,
        "v03.rollup.acc2001": _total_is(out, "rollup", "ACC-2001", "268.75"),
        "v03.rollup.acc2005": _total_is(out, "rollup", "ACC-2005", "64.0"),
        "v03.rollup.acc2007": _total_is(out, "rollup", "ACC-2007", "1310.0"),
        "v03.rollup.acc2010": _total_is(out, "rollup", "ACC-2010", "412.5"),
        "v03.rollup.acc2011": _total_is(out, "rollup", "ACC-2011", "33.0"),
        "v03.rollup.other_month_excluded": None if totals is None
        else "ACC-2009" not in totals,
        "v03.rollup.sorted": None if totals is None
        else list(totals) == sorted(totals),

        # 경보 (6)
        "v03.alerts.runs": out.alerts["ok"] and alerts is not None,
        "v03.alerts.high_usage": _alerted(out, "alerts", "ACC-2007",
                                          "high-usage"),
        "v03.alerts.very_high_usage": _alerted(out, "alerts", "ACC-2007",
                                               "very-high-usage"),
        "v03.alerts.severity": None if not alerts
        else any(a.get("account") == "ACC-2007"
                 and a.get("severity") == "page" for a in alerts
                 if isinstance(a, dict)),
        "v03.alerts.quiet_account": None if alerts is None
        else not any(a.get("account") == "ACC-2005" for a in alerts
                     if isinstance(a, dict)),
        "v03.alerts.sorted": None if alerts is None
        else alerts == sorted(alerts, key=lambda a: (str(a.get("account")),
                                                     str(a.get("rule")))),

        # 내보내기 (6)
        "v03.export.json_runs": out.export_json["ok"]
        and export_json is not None,
        "v03.export.json_month": None if not isinstance(export_json, dict)
        else export_json.get("month") == MONTH,
        "v03.export.json_rows": None if not isinstance(export_json, dict)
        else any(isinstance(r, dict) and r.get("account") == "ACC-2007"
                 and _same(r.get("quantity"), "1310.0")
                 for r in (export_json.get("rows") or [])),
        "v03.export.csv_runs": out.export_csv["ok"] and bool(csv_lines),
        "v03.export.csv_header": None if not csv_lines
        else csv_lines[0].replace(" ", "") == "account,quantity",
        "v03.export.csv_rows": None if len(csv_lines) < 2
        else any(line.startswith("ACC-2007,")
                 and _same(line.split(",")[1], "1310.0")
                 for line in csv_lines[1:]),
    }


def v04_checks(out: Outputs) -> dict:
    """v0.4 — 정정과 as-of. **평평한 기록으로는 통과할 수 없다.**"""
    asof_totals = out.totals("rollup_asof")
    early = out.totals("rollup_early")
    boundary = out.totals("rollup_boundary")
    export_asof = _json(out.export_asof)
    export_plain = _json(out.export_json)
    rollup_data = _json(out.rollup)
    alerts_data = _json(out.alerts)

    return {
        # 정정 (12)
        "v04.corr.acc2002": _total_is(out, "rollup", "ACC-2002", "275.5"),
        "v04.corr.acc2004": _total_is(out, "rollup", "ACC-2004", "410.0"),
        "v04.corr.acc2008": _total_is(out, "rollup", "ACC-2008", "513.0"),
        "v04.corr.chain_last_wins": _total_is(out, "rollup", "ACC-2003",
                                              "101.25"),
        "v04.corr.unknown_target_ignored": _total_is(out, "rollup",
                                                     "ACC-2006", "220.0"),
        "v04.corr.unknown_target_reported":
            _skip_has(out, "unknown correction target"),
        "v04.corr.unknown_target_line":
            _skip_has(out, "site-b-2026-09.jsonl:2:"),
        "v04.corr.uncorrected_untouched":
            _total_is(out, "rollup", "ACC-2001", "268.75"),
        "v04.corr.alerts_follow": None if out.alert_list() is None
        else not any(a.get("account") == "ACC-2004"
                     for a in out.alert_list() if isinstance(a, dict)),
        "v04.corr.alerts_keep_real": _alerted(out, "alerts", "ACC-2008",
                                              "high-usage"),
        "v04.corr.export_follows": None if not isinstance(export_plain, dict)
        else any(isinstance(r, dict) and r.get("account") == "ACC-2002"
                 and _same(r.get("quantity"), "275.5")
                 for r in (export_plain.get("rows") or [])),
        "v04.corr.csv_follows": None if not out.export_csv["ok"]
        else any(line.startswith("ACC-2004,")
                 and _same(line.split(",")[1], "410.0")
                 for line in (out.export_csv["stdout"] or "").splitlines()),

        # as-of (14)
        "v04.asof.rollup_runs": out.rollup_asof["ok"]
        and asof_totals is not None,
        "v04.asof.late_row_excluded": _total_is(out, "rollup_asof",
                                                "ACC-2001", "250.0"),
        "v04.asof.correction_not_yet": _total_is(out, "rollup_asof",
                                                 "ACC-2002", "300.0"),
        "v04.asof.mid_chain": _total_is(out, "rollup_asof", "ACC-2003",
                                        "95.0"),
        "v04.asof.pre_correction": _total_is(out, "rollup_asof", "ACC-2004",
                                             "640.0"),
        "v04.asof.in_month_correction": _total_is(out, "rollup_asof",
                                                  "ACC-2008", "513.0"),
        "v04.asof.alerts_as_of": _alerted(out, "alerts_asof", "ACC-2004",
                                          "high-usage"),
        "v04.asof.alerts_as_of_runs": out.alerts_asof["ok"]
        and out.alert_list("alerts_asof") is not None,
        "v04.asof.early_only_two": None if early is None
        else set(early) == {"ACC-2001", "ACC-2002"},
        "v04.asof.early_values": None if early is None
        else (_same(early.get("ACC-2001"), "110.0")
              and _same(early.get("ACC-2002"), "300.0")),
        "v04.asof.boundary_inclusive": None if boundary is None
        else _same(boundary.get("ACC-2006"), "220.0"),
        "v04.asof.export_carries_as_of":
            None if not isinstance(export_asof, dict) else
            export_asof.get("as_of") == AS_OF_MONTH_END,
        "v04.asof.export_as_of_null":
            None if not isinstance(export_plain, dict) else
            "as_of" in export_plain and export_plain.get("as_of") is None,
        "v04.asof.rollup_reports_as_of":
            None if not isinstance(rollup_data, dict) else
            "as_of" in rollup_data and rollup_data.get("as_of") is None,

        # 기록이 담고 있는 것이 산출물에 드러나는가 (8)
        "v04.shape.emits_id": _reading_key(out, "id"),
        "v04.shape.emits_observed_at": _reading_key(out, "observed_at"),
        "v04.shape.emits_recorded_at": _reading_key(out, "recorded_at"),
        "v04.shape.emits_corrects": _reading_key(out, "corrects"),
        "v04.shape.recorded_at_real": None if not out.readings()
        else any(isinstance(r, dict)
                 and str(r.get("recorded_at", "")).startswith("2026-10")
                 for r in out.readings()),
        "v04.shape.corrects_real": None if not out.readings()
        else any(isinstance(r, dict) and r.get("corrects") == "h03"
                 for r in out.readings()),
        "v04.shape.alerts_report_as_of":
            None if not isinstance(alerts_data, dict) else
            "as_of" in alerts_data,
        "v04.shape.visible_tests_pass": out.tests["ok"],
    }


def v05_checks(out: Outputs) -> dict:
    """v0.5 — 감사. **출처를 안 달고 있으면 통과할 수 없다.**"""
    trail = _audit(out, "audit_2003")
    sources = _sources(out, "audit_2003")
    trail_2008 = _audit(out, "audit_2008")
    sources_2008 = _sources(out, "audit_2008")
    missing = _audit(out, "audit_missing")
    h05 = _source_row(out, "audit_2003", "h05")
    h07 = _source_row(out, "audit_2003", "h07")
    j04 = _source_row(out, "audit_2008", "j04")

    return {
        # 감사 (18)
        "v05.audit.runs": out.audit_2003["ok"] and trail is not None,
        "v05.audit.reports_account": None if not isinstance(trail, dict)
        else trail.get("account") == "ACC-2003",
        "v05.audit.reports_month": None if not isinstance(trail, dict)
        else trail.get("month") == MONTH,
        "v05.audit.quantity_matches_rollup": None if not isinstance(trail, dict)
        else _same(trail.get("quantity"), "101.25"),
        "v05.audit.has_sources": None if sources is None else len(sources) == 3,
        "v05.audit.source_ids": None if sources is None
        else {r.get("id") for r in sources if isinstance(r, dict)} == {
            "h05", "h06", "h07"},
        "v05.audit.superseded_marked": None if h05 is None
        else h05.get("superseded_by") == "h06",
        "v05.audit.latest_not_superseded": None if h07 is None
        else h07.get("superseded_by") is None,
        "v05.audit.source_file": None if h05 is None
        else h05.get("file") == "site-a-2026-09.csv",
        "v05.audit.source_line_csv": None if h05 is None
        else h05.get("line") == 6,
        "v05.audit.source_quantity": None if h05 is None
        else _same(h05.get("quantity"), "80.0"),
        "v05.audit.sorted": None if not sources
        else sources == sorted(
            sources, key=lambda r: (str(r.get("file")), r.get("line") or 0)),
        "v05.audit.as_of_applies": None if not isinstance(trail_2008, dict)
        else _same(trail_2008.get("quantity"), "513.0"),
        "v05.audit.as_of_sources": None if sources_2008 is None
        else len(sources_2008) == 3,
        "v05.audit.source_line_jsonl": None if j04 is None
        else j04.get("line") == 4,
        "v05.audit.jsonl_superseded": None if j04 is None
        else j04.get("superseded_by") == "j05",
        "v05.audit.unknown_account_empty": None if not isinstance(missing, dict)
        else (missing.get("sources") == []
              and _same(missing.get("quantity"), "0")),
        "v05.audit.month_filter": None if sources is None
        else all(isinstance(r, dict) and r.get("id") != "h14"
                 for r in sources),

        # 출처 (8)
        "v05.prov.emits_source": _reading_key(out, "source"),
        "v05.prov.source_has_file": None if not out.readings()
        else all(isinstance((r or {}).get("source"), dict)
                 and "file" in r["source"] for r in out.readings()
                 if isinstance(r, dict)),
        "v05.prov.source_has_line": None if not out.readings()
        else all(isinstance((r or {}).get("source"), dict)
                 and "line" in r["source"] for r in out.readings()
                 if isinstance(r, dict)),
        "v05.prov.csv_lines_start_at_two": None if not out.readings()
        else any(isinstance(r, dict) and r.get("id") == "h01"
                 and (r.get("source") or {}).get("line") == 2
                 for r in out.readings()),
        "v05.prov.jsonl_lines_start_at_one": None if not out.readings()
        else any(isinstance(r, dict) and r.get("id") == "j01"
                 and (r.get("source") or {}).get("line") == 1
                 for r in out.readings()),
        "v05.prov.file_is_basename": None if not out.readings()
        else all("/" not in str((r.get("source") or {}).get("file", ""))
                 and "\\" not in str((r.get("source") or {}).get("file", ""))
                 for r in out.readings() if isinstance(r, dict)),
        "v05.prov.both_feeds_tracked": None if not out.readings()
        else {str((r.get("source") or {}).get("file")) for r in out.readings()
              if isinstance(r, dict)} == {"site-a-2026-09.csv",
                                          "site-b-2026-09.jsonl"},
        "v05.prov.audit_ids_match_intake": None if sources is None
        or not out.readings() else all(
            any(isinstance(x, dict) and x.get("id") == r.get("id")
                for x in out.readings())
            for r in sources if isinstance(r, dict)),
    }


def checkpoints(work_dir: Path) -> dict[str, bool | None]:
    work_dir = Path(work_dir)
    with tempfile.TemporaryDirectory() as tmp:
        data = Path(tmp) / "data"
        data.mkdir()
        for path in sorted(HIDDEN.iterdir()):
            if path.is_file():
                shutil.copy(path, data / path.name)
        out = Outputs(work_dir, data)
        result: dict[str, bool | None] = {}
        for block in (v03_checks(out), v04_checks(out), v05_checks(out)):
            result.update(block)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("work_dir", type=Path, nargs="?")
    parser.add_argument("--work-dir", dest="named", type=Path)
    args = parser.parse_args()
    work_dir = args.work_dir or args.named
    if work_dir is None:
        parser.error("작업 디렉토리를 위치 인자나 --work-dir 로 준다")
    result = {"task": "record-shape", "checkpoints": checkpoints(work_dir)}
    print(json.dumps(result, ensure_ascii=False))
    return 0


# **진입점은 파일 맨 끝에 둔다.** 새 채점 함수를 이 아래에 붙이면 임포트하는
# 테스트는 통과하고 스크립트로 부르는 수집만 터진다. 2026-08-21에 실제로
# 그렇게 됐다.
if __name__ == "__main__":
    raise SystemExit(main())
