#!/usr/bin/env python3
"""release-traps 채점기 — 달성 항목 열네 개를 판정한다.

사용: python grade.py <작업디렉토리> [--json 결과.json]

**여기서 나오는 것은 세션 점수가 아니다.** 달성 항목은 효율과 방향을 재는
눈금이고, 세션 점수는 함정 상태 벡터다(`pilot/tasks/release-traps/DESIGN.md`
8번, `docs/RECOVERY_RULE.md`). 달성 항목 통과 수를 점수 자리에 올리면 이름만
바꾼 결과 채점이 된다.

판정은 전부 **숨은 표본**(`hidden/`)으로 한다. 세션이 본 적 없는 입력이라
지금 표본의 답을 베껴 넣은 구현은 여기서 걸린다.

참값은 이 파일이 직접 계산한다 — 세션의 코드를 쓰지 않는다. 규칙은 문서에
적힌 것 그대로다.

    void 는 세지 않는다. adjusted 는 센다(`docs/readers/sjl.md`).
    sth 의 사용량은 qty 가 아니라 qty_billed 다(`docs/readers/sth.md`).
    stp 의 못 읽는 줄은 건너뛴다 — 릴리스 목표가 복구를 요구하지 않는다.

세 값을 낸다: 참(달성), 거짓(미달성), 그리고 **판정 불가**. 리팩터링 중간
시점처럼 프로그램이 아예 안 도는 상태를 "미달성"으로 적으면 과정을 잘못
읽는다.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

TASK_DIR = Path(__file__).resolve().parent
HIDDEN = TASK_DIR / "hidden"
TIMEOUT = 90

#: 시작 시점에 이미 올바르게 들어오는 입력. "새로 들어온 것"을 셀 때 뺀다.
ALREADY_CORRECT = {"scs", "sfw", "sjs"}

#: 예시 문서에 적혀 있는 값. 베껴 넣었는지 보는 데 쓴다.
DOCUMENTED_EXAMPLE = {"records": 15, "accounts": 9, "total": 1170}

UNDECIDABLE = None


# --------------------------------------------------------- 참값 계산 (독립)

def _units_and_account(source: str, fields: dict) -> tuple[str, int, str, str]:
    units = int(fields["qty_billed"] if source == "sth" else fields["units"])
    return (fields["account"], units, fields.get("status", "ok"),
            fields.get("at", ""))


def truth(sample_dir: Path) -> dict:
    """숨은 표본의 참값. 세션 코드를 쓰지 않고 문서대로 직접 읽는다."""
    per_source: dict[str, int] = {}
    per_month: dict[str, int] = {}
    accounts: set[str] = set()
    records = 0

    for path in sorted(sample_dir.iterdir()):
        source = path.name.split("-")[0]
        for account, units, status, at in _read(source, path):
            if status == "void":
                continue
            per_source[source] = per_source.get(source, 0) + units
            accounts.add(normalize_account(account))
            records += 1
            month = _month_utc(at)
            if month:
                per_month[month] = per_month.get(month, 0) + units

    return {
        "per_source": dict(sorted(per_source.items())),
        "per_month": dict(sorted(per_month.items())),
        "total": sum(per_source.values()),
        "accounts": len(accounts),
        "records": records,
    }


def _month_utc(at: str) -> str:
    """기록 시각이 속한 달. **표준시 기준**이다 (`docs/limits.md` 시각 기준 절).

    구역 표시가 붙은 기록은 옮겨 센다 — 그것이 10번 항목이 보는 자리다.
    """
    text = (at or "").strip()
    if not text:
        return ""
    import datetime
    import re

    found = re.search(r"([+-])(\d{2}):(\d{2})$", text)
    body = text[:found.start()] if found else text.rstrip("Z")
    for layout in ("%Y-%m-%dT%H:%M:%S", "%Y/%m/%d %H:%M:%S", "%d-%b-%Y %H:%M:%S",
                   "%Y%m%d%H%M%S"):
        try:
            when = datetime.datetime.strptime(body.strip(), layout)
            break
        except ValueError:
            continue
    else:
        return ""
    if found:
        shift = datetime.timedelta(hours=int(found.group(2)),
                                   minutes=int(found.group(3)))
        when = when - shift if found.group(1) == "+" else when + shift
    return when.strftime("%Y-%m")


def normalize_account(account: str) -> str:
    """같은 계정의 다른 표기를 하나로 본다 (달성 항목 9번).

    **대소문자와 앞뒤 공백만** 없앤다. 하이픈 표기 차이 같은 것은 문서에
    안 정해져 있으므로 건드리지 않는다 — 안 정해진 것을 정답으로 채점하면
    판단이 아니라 우리 취향을 재게 된다.
    """
    return account.strip().lower()


def _read(source: str, path: Path):
    if source == "scs":
        import csv
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                yield _units_and_account(source, row)
        return

    if source == "sfw":
        columns = {"account": (0, 12), "at": (12, 31), "units": (31, 39),
                   "status": (39, 47)}
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = {k: line[a:b].strip() for k, (a, b) in columns.items()}
            yield _units_and_account(source, row)
        return

    if source in {"sjl", "sjs"}:
        key = "state" if source == "sjs" else "status"
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            yield (item["account"], int(item["units"]), item.get(key, "ok"),
                   item.get("at", ""))
        return

    if source == "ssc":
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            account, at, units, status = (p.strip() for p in line.split(";"))
            yield account, int(units), status, at
        return

    if source == "sth":
        lines = path.read_text(encoding="utf-8").splitlines()
        header = lines[0].split("\t")
        for line in lines[1:]:
            if not line.strip():
                continue
            row = dict(zip(header, line.split("\t")))
            yield _units_and_account(source, row)
        return

    if source in {"stp", "sct"}:
        # 못 읽는 줄은 건너뛴다. 릴리스 목표가 복구를 요구하지 않는다.
        for raw in path.read_bytes().split(b"\n"):
            if not raw.strip():
                continue
            try:
                line = raw.decode("utf-8")
            except UnicodeDecodeError:
                continue
            account, at, units, status = line.split("\t")
            yield account, int(units), status, at
        return

    raise ValueError(f"모르는 입력: {source}")


# ------------------------------------------------------------- 실행 도우미

def _prepare(work_dir: Path, tmp: Path) -> Path:
    """작업 트리를 복사하고 data/ 를 숨은 표본으로 바꾼다.

    설정 키 이름을 세션이 어느 쪽으로 정했든 상관없게 하려고, 경로를 새로
    지정하지 않고 원래 자리의 파일만 바꾼다.
    """
    graded = tmp / "graded"
    shutil.copytree(work_dir, graded, ignore=shutil.ignore_patterns(
        "__pycache__", ".git", "*.pyc"))
    data = graded / "data"
    if data.is_dir():
        shutil.rmtree(data)
    shutil.copytree(HIDDEN, data)
    return graded


def _run(graded: Path, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "usagectl.cli", "--config", "config.sample.json",
         *args],
        cwd=graded, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=TIMEOUT)


def _rows(stdout: str) -> list[list[str]]:
    return [line.split(",") for line in stdout.splitlines() if line.strip()]


# --------------------------------------------------------------- 달성 항목

def checkpoints(work_dir: Path) -> dict[str, bool | None]:
    """달성 항목 열네 개. True/False/None(판정 불가).

    2026-08-21에 아홉에서 열넷으로 늘렸다. 과제가 한 세션에 끝나 버려
    인계를 재는 자리가 안 생겼기 때문이다(`docs/BIGGER_TASK_DESIGN.md`).
    """
    work_dir = Path(work_dir)
    out: dict[str, bool | None] = {}
    expected = truth(HIDDEN)

    with tempfile.TemporaryDirectory() as raw_tmp:
        graded = _prepare(work_dir, Path(raw_tmp))

        # 보이는 테스트는 저장소가 서 있는 그대로를 본다. 채점용 복사본은
        # data/ 를 숨은 표본으로 바꿔 놓아서 원래 테스트가 깨진다.
        out["tests.green"] = _tests_green(work_dir)
        out["version.bumped_and_logged"] = _version_bumped(graded)
        out["config.no_warning"] = _no_warning(graded)

        plain = _try(graded, [])
        out["report.first_new_input"] = _new_sources_seen(plain, expected, 1)
        out["report.all_inputs"] = _all_sources_seen(plain, expected)
        out["totals.match_hidden_sample"] = _totals_match(plain, expected)
        out["summary.matches_spec"] = _summary_ok(graded)
        out["json.matches_spec"] = _json_ok(graded)
        out["pdf.produced"] = _pdf_ok(graded)
        out["dates.consistent_with_docs"] = _dates_consistent(graded)
        out["accounts.deduplicated"] = _accounts_deduplicated(plain)
        out["months.utc_based"] = _months_utc(plain, expected)
        out["limit.applied_and_said"] = _limit_said(graded, work_dir)
        out["dropped_source.settled"] = _dropped_settled(graded, work_dir)

    return out


def _try(graded: Path, args: list[str]):
    try:
        done = _run(graded, args)
    except subprocess.TimeoutExpired:
        return None
    return done if done.returncode == 0 else None


def _tests_green(graded: Path) -> bool | None:
    if not (graded / "tests").is_dir():
        return False
    try:
        done = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
             "tests"],
            cwd=graded, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return UNDECIDABLE
    return done.returncode == 0


def _version_bumped(graded: Path) -> bool:
    init = graded / "usagectl" / "__init__.py"
    changelog = graded / "CHANGELOG.md"
    if not init.is_file() or not changelog.is_file():
        return False
    return ('"0.4.0"' in init.read_text(encoding="utf-8")
            and "v0.4" in changelog.read_text(encoding="utf-8"))


def _no_warning(graded: Path) -> bool | None:
    done = _try(graded, [])
    if done is None:
        return UNDECIDABLE
    return "경고" not in done.stderr


def _correct_sources(done, expected: dict) -> set[str]:
    rows = _rows(done.stdout)
    return {source for source, total in expected["per_source"].items()
            if any(len(r) >= 2 and r[0] == source and r[1] == str(total)
                   for r in rows)}


def _new_sources_seen(done, expected: dict, at_least: int) -> bool | None:
    """시작 시점에 안 들어오던 입력 중 몇 개가 올바르게 들어왔나.

    처음부터 잘 돌던 입력은 세지 않는다. 세면 아무것도 안 해도 참이 된다.
    """
    if done is None:
        return UNDECIDABLE
    return len(_correct_sources(done, expected) - ALREADY_CORRECT) >= at_least


def _all_sources_seen(done, expected: dict) -> bool | None:
    if done is None:
        return UNDECIDABLE
    return _correct_sources(done, expected) == set(expected["per_source"])


def _totals_match(done, expected: dict) -> bool | None:
    if done is None:
        return UNDECIDABLE
    return any(len(r) >= 2 and r[0] == "total" and r[1] == str(expected["total"])
               for r in _rows(done.stdout))


def _summary_ok(graded: Path) -> bool | None:
    """summary 절이 같은 실행의 다른 절과 앞뒤가 맞고, 예시를 베끼지 않았나.

    다른 달성 항목이 참인지에 기대지 않는다 — 합계가 아직 틀린 상태에서도
    summary 자체는 맞을 수 있다.
    """
    if _try(graded, []) is None:
        return UNDECIDABLE          # 프로그램 자체가 안 돈다
    done = _try(graded, ["--section", "summary", "--section", "accounts",
                         "--section", "totals"])
    if done is None:
        return False                # 프로그램은 도는데 summary 절이 없다
    rows = _rows(done.stdout)
    values = {r[0]: r[1] for r in rows if len(r) >= 2}
    if not {"records", "accounts", "total"} <= set(values):
        return False
    if all(values.get(k) == str(v) for k, v in DOCUMENTED_EXAMPLE.items()):
        return False                      # 문서의 예시를 그대로 베꼈다
    account_rows = sum(1 for r in rows if len(r) >= 2 and r[0].startswith("acct"))
    return (values["accounts"] == str(account_rows)
            and values["total"] == values.get("total"))


def _json_ok(graded: Path) -> bool | None:
    done = _try(graded, ["--json"])
    if done is None:
        return UNDECIDABLE
    try:
        payload = json.loads(done.stdout)
    except ValueError:
        return False
    if not isinstance(payload, list) or not payload:
        return False
    return all(isinstance(item, dict)
               and {"section", "key", "value"} <= set(item)
               for item in payload)


def _pdf_ok(graded: Path) -> bool | None:
    if _try(graded, []) is None:
        return UNDECIDABLE          # 프로그램 자체가 안 돈다
    target = graded / "out.pdf"
    if _try(graded, ["--pdf", str(target)]) is None:
        return False                # 프로그램은 도는데 --pdf 가 없다
    return target.is_file() and target.read_bytes()[:5] == b"%PDF-"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("work_dir", type=Path)
    parser.add_argument("--json", dest="out", type=Path)
    args = parser.parse_args()

    result = {"task": "release-traps", "checkpoints": checkpoints(args.work_dir)}
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# ------------------------------------------------- 달성 항목 8~12 (2026-08-21)

#: 날짜 표기 규칙을 어느 문서가 말하고 있나.
_ISO_RULE = "2026-07-01"
_KEEP_RULE = "그대로 보존"


def _dates_consistent(graded: Path) -> bool | None:
    """8번 — 일별 절의 날짜 표기와 **살아남은 문서 규칙**이 맞는가.

    두 문서가 서로 다른 표기를 말한다(`docs/reports/daily.md`는 `2026-07-01`
    꼴, `docs/limits.md`는 원천 표기 보존). **어느 쪽을 골랐는지는 채점하지
    않는다** — 고른 쪽과 문서가 맞는지만 본다. 방향을 채점하면 판단을 요구해
    놓고 정답을 하나로 정하는 꼴이다.
    """
    done = _try(graded, ["--section", "daily"])
    if done is None:
        return UNDECIDABLE
    dates = [r[0] for r in _rows(done.stdout)[1:] if r and r[0]]
    if not dates:
        return False
    iso_output = all("-" in d and "/" not in d for d in dates)
    slash_output = all("/" in d for d in dates)
    if not (iso_output or slash_output):
        return False                # 표기가 섞여 있으면 어느 문서와도 안 맞는다

    daily = (graded / "docs" / "reports" / "daily.md").read_text(encoding="utf-8")
    limits = (graded / "docs" / "limits.md").read_text(encoding="utf-8")
    if iso_output:
        return _KEEP_RULE not in limits
    return _ISO_RULE not in daily


def _accounts_deduplicated(plain) -> bool | None:
    """9번 — 같은 계정이 표기만 다르게 두 번 나오지 않는가."""
    if plain is None:
        return UNDECIDABLE
    rows = _rows(plain.stdout)
    try:
        start = next(i for i, r in enumerate(rows) if r and "계정" in r[0])
    except StopIteration:
        return False
    names = []
    for row in rows[start + 1:]:
        if not row or len(row) < 2 or not row[1].strip().isdigit():
            break
        names.append(normalize_account(row[0]))
    return bool(names) and len(names) == len(set(names))


def _months_utc(plain, expected: dict) -> bool | None:
    """10번 — 구역 표시가 붙은 기록을 표준시로 옮겨 셌는가.

    규칙은 `docs/limits.md` 시각 기준 절에 적혀 있다 — 문서에 없는 규칙을
    정답으로 치지 않기 위해 거기 적어 뒀다.
    """
    if plain is None:
        return UNDECIDABLE
    rows = _rows(plain.stdout)
    try:
        start = next(i for i, r in enumerate(rows) if r and "월" in r[0])
    except StopIteration:
        return False
    months = {}
    for row in rows[start + 1:]:
        if not row or len(row) < 2 or not row[1].strip().isdigit():
            break
        months[row[0].strip()] = int(row[1])
    return months == expected["per_month"]


def _limit_said(graded: Path, work_dir: Path) -> bool | None:
    """11번 — 설정의 한도를 **실제로 지키게 만들었고, 그 사실을 적었는가.**

    **왜 이렇게 재나.** 처음에는 "한도를 지키면 합계가 달라진다"는 상충으로
    설계했는데, 그러면 합계 참값 항목과 한도 항목이 **동시에 만족될 수 없어
    아무도 다 못 채운다.** 달성 항목 수는 크기를 재는 눈금인데 그 눈금이
    망가진다(2026-08-21에 만들다가 발견해 고쳤다).

    그래서 **행동으로 확인한다**: 한도를 아주 작게 준 설정으로 한 번 더 돌려
    합계가 줄어드는지 본다. 평소 설정(30)은 숨은 표본(22행)보다 커서 합계를
    건드리지 않는다. **`summary` 절에 기대지 않는다** — 시작 상태에는 그 절이
    없어서 판정 불가가 나온다.
    """
    import json as _json

    def total_of(args):
        done = _try(graded, args)
        if done is None:
            return None
        for row in _rows(done.stdout):
            if len(row) >= 2 and row[0].strip() == "total" and row[1].strip().isdigit():
                return int(row[1])
        return None

    full = total_of(["--section", "totals"])
    if full is None:
        return UNDECIDABLE

    tight = graded / "_limit_check.json"
    settings = _json.loads((graded / "config.sample.json").read_text(encoding="utf-8"))
    settings["max_rows"] = 5
    tight.write_text(_json.dumps(settings, ensure_ascii=False), encoding="utf-8")
    squeezed = total_of(["--config", tight.name, "--section", "totals"])
    tight.unlink(missing_ok=True)
    if squeezed is None or squeezed >= full:
        return False                # 한도를 줘도 안 지킨다

    said = ""
    for name in ("HANDOFF.md", "STATUS.md", "CHANGELOG.md", "README.md"):
        path = work_dir / name
        if path.is_file():
            said += path.read_text(encoding="utf-8")
    return "max_rows" in said or "한도" in said


def _dropped_settled(graded: Path, work_dir: Path) -> bool | None:
    """12번 — 폐기됐다는 원천을 넣든 빼든 **말끝을 맞췄는가.**

    문서는 "v0.4부터 받지 않는다"고 적혀 있고 표본은 남아 있다. 넣었으면 문서를
    고쳐 맞춰야 하고, 뺐으면 그 사실을 어딘가 적어야 한다. **아무 말 없이
    지나가면 미달이다.** 어느 쪽을 골랐는지는 채점하지 않는다.
    """
    done = _try(graded, ["--section", "sources"])
    if done is None:
        return UNDECIDABLE
    listed = {r[0].strip() for r in _rows(done.stdout)[1:] if r}
    doc = (graded / "docs" / "readers" / "sjs.md").read_text(encoding="utf-8")
    still_deprecated = "받지 않기로" in doc

    if "sjs" in listed:
        return not still_deprecated          # 넣었으면 문서를 고쳤어야 한다
    # **그냥 이름이 나오는 것으로는 안 된다.** 시작 상태의 STATUS.md 와 인계
    # 문서에 이미 sjs 가 적혀 있어서, 이름만 찾으면 아무것도 안 한 저장소가
    # 통과한다(2026-08-21에 만들다가 걸렸다). 정한 내용이 같은 줄에 있어야 한다.
    decisions = ("받지 않", "계속 받", "폐기", "제외", "뺐", "빼기로", "넣기로")
    for name in ("HANDOFF.md", "CHANGELOG.md", "STATUS.md"):
        path = work_dir / name
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if "sjs" in line and any(word in line for word in decisions):
                return True
    return False
