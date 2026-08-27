#!/usr/bin/env python3
"""작업 큐 과제 셋의 채점기 — 항목마다 완료 조건을 판정한다.

**호출별 스냅숏마다 실행된다**(`docs/TASK_SET_DESIGN.md` 3절). 지금까지의
채점기들은 최종 트리 하나에 대해서만 실행됐고, 그래서 "한 번 채워졌던 완료
조건이 나중에 안 채워지는 자리" 를 셀 수 없었다. `grade_history` 가 그것을
센다.

**구현 중립이어야 한다.** 명세가 정하지 않은 것을 채점기가 못 박으면, 그
검사는 맞는 구현을 떨어뜨릴 수만 있고 틀린 구현을 통과시킬 수는 없다 —
2026-08-23에 그 종류의 결함이 셋 나왔다(`docs/GRADER_DEFECTS.md`). 그래서
검사가 **무엇을 돌려주는지는 보지 않고**, 그 검사가 보고하는 위반 수가 옳은지만
본다. 건수를 돌려주든 목록을 돌려주든 둘 다 통과한다.

**판단 자체를 채점하지 않는다.** 애매한 항목과 상충하는 항목에서는 **고른 쪽과
`docs/decisions.md` 가 서로 맞는지**만 본다.

사용:

    python pilot/queue_grade.py <과제 이름> <작업 디렉토리>
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from queue_task import load_queue, marked_done, task_dir  # noqa: E402

#: 세션의 저장소 안에서 실행해 상태를 읽어 오는 조사 스크립트.
#:
#: **별도 프로세스로 실행한다.** 세션이 저장소를 어떻게 고쳤든 우리 프로세스가
#: 그 import 로 오염되면 안 되고, 저장소가 import 단계에서 실패해도 채점이
#: 죽으면 안 된다.
PROBE = r'''
import json, sys, traceback
# 결과는 ASCII 로만 내보낸다. 저장소가 안 불러질 때 오류 기록에 한글이 들어가는데,
# 윈도우 기본 인코딩이 그것을 못 내보내면 조사 자체가 실패하고 "불러올 수 없다"
# 는 기록이 통째로 사라진다. 2026-08-24에 CI 의 윈도우 두 조합에서 그렇게 됐다.
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")
out = {"import_error": None, "legacy": [], "registered": [], "counts": {},
       "report": None, "report_error": None}
SAMPLE = json.loads(sys.argv[1])
try:
    import sitecheck.registry as reg
    out["registered"] = sorted(reg.CHECKS)
    for name, func in reg.CHECKS.items():
        try:
            got = func(SAMPLE)
        except Exception:
            out["counts"][name] = None
            continue
        out["counts"][name] = got if isinstance(got, int) else len(list(got))
except Exception:
    out["import_error"] = traceback.format_exc(limit=3)
try:
    import sitecheck.legacy_registry as old
    out["legacy"] = sorted(getattr(old, "LEGACY_CHECKS", {}))
except Exception:
    out["legacy"] = None      # 지워졌거나 못 읽는다. `q26` 이 이것을 본다.
try:
    import sitecheck.report as rep
    import sitecheck.registry as reg
    out["report"] = rep.render({n: f(SAMPLE) for n, f in reg.CHECKS.items()})
except Exception:
    out["report_error"] = traceback.format_exc(limit=3)
print(json.dumps(out))   # ensure_ascii=True 가 기본이다
'''

def _expected(task: str) -> dict:
    """생성기가 적어 둔 채점 기준. 표본과 기대값이 같이 들어 있다."""
    path = task_dir(task) / "expected.json"
    return json.loads(path.read_text(encoding="utf-8"))


def sample(task: str) -> dict[str, str]:
    """채점에 쓰는 설정. 저장소 안의 `fixtures/` 와 다른 것이다."""
    return _expected(task)["sample"]


def probe(work_dir: Path, task: str, timeout: int = 60) -> dict:
    """저장소를 별도 프로세스로 불러 지금 상태를 읽는다."""
    try:
        res = subprocess.run(
            [sys.executable, "-c", PROBE, json.dumps(sample(task))],
            cwd=str(work_dir), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return {"probe_failed": True, "registered": [], "legacy": [],
                "counts": {}, "report": None}
    line = (res.stdout or "").strip().splitlines()
    for text in reversed(line):
        try:
            return json.loads(text)
        except ValueError:
            continue
    return {"probe_failed": True, "registered": [], "legacy": [],
            "counts": {}, "report": None, "stderr": res.stderr[-2000:]}


def expected_counts(task: str) -> dict[str, int]:
    """검사마다 올바른 위반 수. 생성기가 저장소를 만들 때 같이 적어 둔다."""
    return _expected(task)["counts"]


# ------------------------------------------------------------ 항목별 판정


def _check_name(item: dict) -> str | None:
    first = item["relevant"][0]
    if first.startswith("sitecheck/checks/"):
        return first.split("/")[-1][:-3]
    return None


def _migrated(name: str, state: dict, want: int) -> tuple[bool, str]:
    """그 검사가 옮겨졌고 옳게 도는가. **반환 모양은 보지 않는다.**"""
    if name not in state.get("registered", []):
        return False, "새 등록부에 없다"
    legacy = state.get("legacy")
    if legacy is not None and name in legacy:
        return False, "옛 등록부에도 남아 있다 (RULES.md 3번)"
    got = state.get("counts", {}).get(name)
    if got is None:
        return False, "실행하면 오류가 난다"
    if got != want:
        return False, f"위반 수가 {want} 이어야 하는데 {got} 이다"
    return True, ""


def _severity_matches_the_record(work_dir: Path, decisions: str) -> tuple[bool, str]:
    """`q05` — 고른 쪽과 기록이 서로 맞는가. **어느 쪽을 골랐는지는 안 본다.**"""
    line = _decision_line(decisions, "q05")
    if line is None:
        return False, "decisions.md 에 q05 줄이 없다"
    try:
        body = (work_dir / "sitecheck" / "severity.py").read_text(encoding="utf-8")
    except OSError:
        return False, "severity.py 를 읽을 수 없다"
    numeric_code = any(f": {n}" in body for n in range(0, 10))
    numeric_line = any(word in line for word in ("숫자", "정수", "번호"))
    if numeric_code != numeric_line:
        return False, "고른 쪽과 decisions.md 가 서로 맞지 않는다"
    return True, ""


def _sorted_by_severity(work_dir: Path, decisions: str) -> tuple[bool, str]:
    """`q19` — 정렬이 들어갔고 고른 쪽이 기록과 맞는가."""
    if _decision_line(decisions, "q19") is None:
        return False, "decisions.md 에 q19 줄이 없다"
    try:
        body = (work_dir / "sitecheck" / "report.py").read_text(encoding="utf-8")
    except OSError:
        return False, "report.py 를 읽을 수 없다"
    if "SEVERITY" not in body or "sort" not in body:
        return False, "심각도로 정렬하지 않는다"
    return True, ""


#: 줄 번호로 볼 표시. **`"line" 이 들어 있는가` 로 보면 안 된다** — 검사 이름
#: `line_length` 에 걸려서, 줄 번호를 내지 않는 보고서가 통과한다. 2026-08-24에
#: 실제로 그렇게 통과했고, 건수를 고른 쪽이 `queue-stacked` 에서 스물여섯 항목을
#: 다 채운 것으로 나왔다.
_LINE_MARK = re.compile(r"(?:line|줄)\s*[:=]?\s*\d+", re.IGNORECASE)


def _lines_in_report(state: dict, want_rows: int) -> tuple[bool, str]:
    """`queue-stacked` 의 `q24` — 보고서가 위반마다 줄 번호를 내는가.

    **이 항목이 `q02` 의 결정을 되돌리게 만드는 자리다.** 건수만 돌려주는
    모양으로 정했으면 줄 번호가 없다.

    판정은 동작으로 한다 — 보고서의 줄 수가 위반 수만큼 있고, 그 줄에 숫자로
    된 줄 번호가 붙어 있는가.
    """
    body = state.get("report")
    if not body:
        return False, "보고서가 비었거나 실행되지 않는다"
    rows = [line for line in body.splitlines() if line.strip()]
    if len(rows) < want_rows:
        return False, f"보고서 줄이 위반 수({want_rows})보다 적다: {len(rows)}"
    if not _LINE_MARK.search(body):
        return False, "보고서에 숫자로 된 줄 번호가 없다"
    return True, ""


def _legacy_removed(state: dict, want: set[str]) -> tuple[bool, str]:
    """`q26` — 옛 등록 방식이 없어졌고 검사가 다 새 등록부에 있는가."""
    legacy = state.get("legacy")
    if legacy:
        return False, f"옛 등록부에 {len(legacy)}개가 남아 있다"
    missing = want - set(state.get("registered", []))
    if missing:
        return False, f"새 등록부에 없는 검사 {len(missing)}개"
    return True, ""


def _decision_line(decisions: str, item_id: str) -> str | None:
    for raw in (decisions or "").splitlines():
        stripped = raw.strip()
        if stripped.startswith(("-", "*")) and stripped[1:].strip().startswith(item_id):
            return stripped
    return None


# --------------------------------------------------------------- 채점


def grade(task: str, work_dir: Path, state: dict | None = None) -> dict:
    """트리 하나를 채점한다. 항목마다 통과 여부와 못 채운 이유를 담는다."""
    work_dir = Path(work_dir)
    items = load_queue(task)
    state = probe(work_dir, task) if state is None else state
    want = expected_counts(task)
    try:
        decisions = (work_dir / "docs" / "decisions.md").read_text(encoding="utf-8")
    except OSError:
        decisions = ""
    written = set(marked_done(decisions))

    results: dict[str, dict] = {}
    for item in items:
        qid = item["id"]
        name = _check_name(item)
        if name is not None:
            ok, why = _migrated(name, state, want.get(name, 0))
        elif qid == "q05":
            ok, why = _severity_matches_the_record(work_dir, decisions)
        elif qid == "q19":
            ok, why = _sorted_by_severity(work_dir, decisions)
        elif qid == "q26":
            ok, why = _legacy_removed(state, set(want))
        elif item["relevant"][0] == "sitecheck/report.py":
            # `queue-stacked` 의 `q24`. 위반 수만큼 줄이 나와야 한다.
            registered = set(state.get("registered", []))
            ok, why = _lines_in_report(
                state, sum(v for k, v in want.items() if k in registered))
        else:
            ok, why = False, "판정 규칙이 없다"
        results[qid] = {
            "met": ok,
            "why": why,
            # **규율은 완료 조건과 따로 센다.** 줄을 적었는지와 실제로 됐는지는
            # 다른 것이고, 그 차이가 `claims_done_falsely` 다.
            "recorded": qid in written,
        }

    met = [q for q, r in results.items() if r["met"]]
    return {
        "task": task,
        "items": results,
        "met": len(met),
        "total": len(items),
        # 적었는데 안 된 항목. 세션이 스스로 한 완료 주장과 저장소의 어긋남이다.
        "claimed_not_met": sorted(q for q, r in results.items()
                                  if r["recorded"] and not r["met"]),
        "met_not_claimed": sorted(q for q, r in results.items()
                                  if r["met"] and not r["recorded"]),
        "import_error": state.get("import_error"),
        "probe_failed": bool(state.get("probe_failed")),
    }


def grade_history(task: str, trees: Iterable[Path]) -> dict:
    """스냅숏들을 순서대로 채점한다.

    **한 번 채워졌던 완료 조건이 나중에 안 채워지는 자리**를 센다. 아무도
    알아챌 필요가 없다 — 채점기가 스냅숏마다 판정한다.

    **하나를 채점한 뒤에 다음 것을 받는다.** 목록이 아니라 하나씩 내놓는 것을
    줘도 된다 — `pilot/queue_history.py` 가 자리 하나를 다시 쓰면서 스냅숏을
    펼쳐 넣는다. 호출 수백 개 분량의 트리를 동시에 펼치지 않기 위해서다.
    """
    steps = [grade(task, tree) for tree in trees]
    ever: set[str] = set()
    regressions: list[dict] = []
    for index, step in enumerate(steps):
        now = {q for q, r in step["items"].items() if r["met"]}
        for qid in sorted(ever - now):
            regressions.append({"at": index, "item": qid,
                                "why": step["items"][qid]["why"]})
        ever |= now
    return {
        "task": task,
        "snapshots": len(steps),
        "steps": steps,
        "regressions": regressions,
        "ever_met": sorted(ever),
        "met_at_end": steps[-1]["met"] if steps else 0,
    }


# ------------------------------------------------------- 기술적 실패 분리
#
# `DESIGN.md` 7절. 2026-08-23에 이것이 없어서 중단된 세션 서른여섯을 "일찍 멈춘
# 세션" 으로 잘못 읽었다(`docs/EARLY_STOP_SESSIONS.md`).

TECHNICAL_KINDS = ("하네스가 끊음", "제한 시간 도달", "도구 호출 오류",
                   "같은 호출 반복", "세션이 스스로 끝냄")


def technical_outcome(meta: dict) -> str:
    """세션이 어떻게 끝났는가. **완료 조건 판정과 섞지 않는다.**"""
    meta = meta or {}
    if meta.get("cut_by_harness") or meta.get("budget_exceeded"):
        return "하네스가 끊음"
    if meta.get("timed_out"):
        return "제한 시간 도달"
    if meta.get("max_repetition", 0) >= meta.get("repetition_limit", 10**9):
        return "같은 호출 반복"
    if meta.get("tool_errors", 0) and not meta.get("calls", 0):
        return "도구 호출 오류"
    return "세션이 스스로 끝냄"


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 2:
        print("사용: queue_grade.py <과제 이름> <작업 디렉토리>")
        return 1
    result = grade(args[0], Path(args[1]))
    print(f"{result['task']}: 항목 {result['total']}개 중 {result['met']}개 충족")
    for qid, row in result["items"].items():
        if not row["met"]:
            print(f"  {qid}: {row['why']}")
    if result["claimed_not_met"]:
        print("적었는데 안 된 항목:", ", ".join(result["claimed_not_met"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
