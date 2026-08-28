#!/usr/bin/env python3
"""작업 큐 과제 `queue-flat` 의 채점기 — 항목마다 완료 조건을 판정한다.

**호출별 스냅숏마다 실행된다**(`pilot/tasks/queue-flat/DESIGN.md` 6절). 지금까지의
채점기들은 최종 트리 하나에 대해서만 실행됐고, 그래서 "한 번 채워졌던 완료
조건이 나중에 안 채워지는 자리" 를 셀 수 없었다. `grade_history` 가 그것을
센다.

**구현 중립이어야 한다.** 명세가 정하지 않은 것을 채점기가 못 박으면, 그
검사는 맞는 구현을 떨어뜨릴 수만 있고 틀린 구현을 통과시킬 수는 없다 —
2026-08-23에 그 종류의 결함이 셋 나왔다(`docs/GRADER_DEFECTS.md`). 그래서
검사가 **무엇을 돌려주는지는 보지 않고**, 그 검사가 보고하는 위반 수가 옳은지만
본다. 건수를 돌려주든 목록을 돌려주든 둘 다 통과한다.

**판단 자체를 채점하지 않는다.** 세션이 정해야 하는 항목(`q05`)에서는 **저장소에
심각도 사이의 순서가 정해졌는지**만 본다 — 표시를 숫자로 바꾸든 문자열을 두고
순서를 따로 두든 통과한다.

**글자로 판정하지 않는다** (2026-08-28, `docs/QUEUE_TASK_DEFECTS.md` 4절).
앞 판은 `q05` 를 `docs/decisions.md` 의 한국어 낱말 셋으로, `q19` 를
`sitecheck/report.py` 안의 글자 둘로 판정했다. 지금은 둘 다 저장소를 실제로
불러서 본다.

**완료 조건에 `docs/decisions.md` 의 줄을 넣지 않는다.** 줄을 적었는지는
`recorded` 로 따로 세고, 그 차이가 `claimed_not_met` 이다. 앞 판은 `q05` 와
`q19` 만 줄을 완료 조건에 넣어서 나머지 스물넷과 판정 기준이 달랐다.

사용:

    python pilot/queue_grade.py <과제 이름> <작업 디렉토리>
"""

from __future__ import annotations

import json
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
       "report": None, "report_error": None, "severity": None}
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
    # `q05` — 심각도 사이의 순서가 저장소에 정해져 있는가. **글자가 아니라
    # 모듈이 실제로 무엇을 갖고 있는지로 본다.** 표시를 숫자로 바꾸는 것도,
    # 문자열은 두고 순서를 따로 두는 것도 맞는 답이다.
    import sitecheck.severity as sev
    values = list(getattr(sev, "SEVERITY", {}).values())
    extra = []
    for _n in dir(sev):
        if _n.startswith("_") or _n == "SEVERITY":
            continue
        _v = getattr(sev, _n)
        if isinstance(_v, (dict, list, tuple, set)):
            extra.append(_n)
        elif callable(_v) and getattr(_v, "__module__", "") == sev.__name__:
            extra.append(_n)
    out["severity"] = {
        "values_all_str": all(isinstance(v, str) for v in values),
        "extra_names": sorted(extra),
    }
except Exception:
    out["severity"] = None
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


def _severity_is_ordered(state: dict) -> tuple[bool, str]:
    """`q05` — 심각도 사이의 순서가 저장소에 정해져 있는가.

    **어느 쪽을 골랐는지는 보지 않는다.** 표시를 숫자로 바꾸는 것도, 문자열은
    그대로 두고 순서를 따로 두는 것도(순서 표, 차례 목록, 등급 함수) 맞는
    답이다. 시작 상태는 문자열 셋뿐이고 그 사이의 순서가 없다.

    **글자로 판정하지 않는다** (2026-08-28, `docs/QUEUE_TASK_DEFECTS.md` 4-1).
    앞 판은 `docs/decisions.md` 의 줄에 `숫자`·`정수`·`번호` 중 하나가 있는지를
    보았고, 같은 결정을 다른 말로 적으면 떨어졌다. 지금은 조사 스크립트가
    `sitecheck/severity.py` 를 실제로 불러 무엇이 들어 있는지 본다.
    """
    got = state.get("severity")
    if got is None:
        return False, "severity.py 를 불러올 수 없다"
    if not got.get("values_all_str"):
        return True, ""
    if got.get("extra_names"):
        return True, ""
    return False, "심각도 사이의 순서가 정해져 있지 않다"


def report_rows(body: str, names: set[str]) -> list[str]:
    """보고서에서 검사 이름을 나온 순서대로 뽑는다. 못 찾은 줄은 건너뛴다."""
    found = []
    for line in (body or "").splitlines():
        if not line.strip():
            continue
        hit = [n for n in names if n in line]
        if hit:
            # 이름 하나가 다른 이름의 일부인 경우가 없으므로 가장 긴 것을 쓴다.
            found.append(max(hit, key=len))
    return found


def _sorted_by_severity(state: dict, groups: dict[str, str]) -> tuple[bool, str]:
    """`q19` — 보고가 심각도 순으로 나오는가. **동작으로 판정한다.**

    같은 심각도의 검사들이 보고서에서 붙어 나오면 통과한다. 어느 심각도가
    먼저인지는 보지 않고, 정렬이 어느 파일에 있는지도 보지 않는다.

    **무리는 시작 상태의 것을 쓴다**(`expected.json` 의 `severity`). 세션이
    표시를 숫자로 바꾸든 이름을 바꾸든 어느 검사가 같은 무리인지는 그대로다.

    **글자로 판정하지 않는다** (2026-08-28, `docs/QUEUE_TASK_DEFECTS.md` 4-2).
    앞 판은 `sitecheck/report.py` 안에 `SEVERITY` 와 `sort` 라는 글자가 있는지만
    보았고, 정렬을 다른 파일에 둔 구현이 떨어졌다.
    """
    body = state.get("report")
    if not body:
        return False, "보고서가 비었거나 실행되지 않는다"
    names = report_rows(body, set(groups))
    if len(names) < 2:
        return False, "보고서에서 검사 이름을 두 개 넘게 못 찾았다"
    seen: list[str] = []
    for name in names:
        label = groups[name]
        if seen and seen[-1] == label:
            continue
        if label in seen:
            return False, f"심각도 {label} 가 보고서에서 떨어져 나온다"
        seen.append(label)
    if len(seen) < 2:
        return False, "보고서에 심각도가 한 종류만 나온다"
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
            ok, why = _severity_is_ordered(state)
        elif qid == "q19":
            ok, why = _sorted_by_severity(state, _expected(task)["severity"])
        elif qid == "q26":
            ok, why = _legacy_removed(state, set(want))
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
    broken: set[str] = set()
    regressions: list[dict] = []
    for index, step in enumerate(steps):
        now = {q for q, r in step["items"].items() if r["met"]}
        # **깨진 자리 하나를 한 번만 센다.** 앞서는 스냅숏마다 다시 세어서,
        # 오래 안 고친 자리 하나가 여러 건으로 보고됐다
        # (`docs/QUEUE_TASK_DEFECTS.md` 5-2). 다시 채워졌다가 또 깨지면
        # 그때는 새로 센다.
        for qid in sorted(ever - now - broken):
            regressions.append({"at": index, "item": qid,
                                "why": step["items"][qid]["why"]})
        broken = (broken | (ever - now)) - now
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
# `pilot/tasks/queue-flat/DESIGN.md` 7절. 2026-08-23에 이것이 없어서 중단된 세션
# 서른여섯을 "일찍 멈춘 세션" 으로 잘못 읽었다(`docs/EARLY_STOP_SESSIONS.md`).
#
# **`pilot/run_chain.py` 가 세션마다 이것을 불러 기록에 `outcome` 으로 적는다.**
# 2026-08-28 전에는 부르는 곳이 시험뿐이었고, 받는 열쇠 이름도 러너가 적는
# 이름과 달랐다(`docs/QUEUE_TASK_DEFECTS.md` 3-3).

TECHNICAL_KINDS = ("하네스가 끊음", "제한 시간 도달", "도구 호출 오류",
                   "같은 호출 반복", "세션이 스스로 끝냄")

#: 같은 호출이 이만큼 되풀이되면 그것으로 끝난 것으로 본다.
#: `harness/gates.json` 의 `repeat_check` 와는 다른 값이다 — 이쪽은 연구 대상
#: 세션이고 그쪽은 우리 세션이다.
REPETITION_LIMIT = 10


def technical_outcome(row: dict, limit: int = REPETITION_LIMIT) -> str:
    """세션이 어떻게 끝났는가. **완료 조건 판정과 섞지 않는다.**

    `pilot/run_chain.py` 가 세션마다 쓰는 기록을 그대로 받는다 — `cut`,
    `timed_out`, 그리고 `audit.metrics` 의 `consecutive_repetition` 과
    `n_tool_calls` 와 `tool_error_rate`.
    """
    row = row or {}
    metrics = (row.get("audit") or {}).get("metrics") or {}
    if row.get("cut") or row.get("budget_exceeded"):
        return "하네스가 끊음"
    if row.get("timed_out"):
        return "제한 시간 도달"
    if metrics.get("consecutive_repetition", 0) >= limit:
        return "같은 호출 반복"
    calls = metrics.get("n_tool_calls", 0)
    if calls and metrics.get("tool_error_rate", 0) >= 1.0:
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
