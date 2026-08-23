#!/usr/bin/env python3
"""배치 하나의 숫자 요약을 마크다운으로 낸다.

**왜 이 파일이 따로 있나.** `results/`는 gitignore 대상이고 컨테이너가
사라지면 원자료도 같이 사라진다. 그래서 배치가 끝나면 숫자를 저장소에
남겨야 한다(`docs/BIGGER_TASK_PREDICTIONS.md` 6절 5번).

**왜 결과를 보기 전에 쓰나.** 무엇을 적을지 데이터를 보고 정하면, 잘 나온
숫자만 적게 된다. 봉인한 예측 여섯 개를 이 파일에 코드로 박아 두고, 배치가
끝나면 그대로 돌린다. 예측 문장과 문턱은 `docs/BIGGER_TASK_PREDICTIONS.md`
3절에서 그대로 옮긴 것이며, 이 파일에서 고치지 않는다.

**빗나간 것을 먼저 적는다** — 출력에서 빗나간 예측이 위로 온다. 봉인 문서
6절 6번이 요구한 것이다.

사용:

    .venv/bin/python pilot/analysis/batch_summary.py results/chain5/release-traps \\
        --task pilot/tasks/release-traps > docs/BIGGER_TASK_RESULTS.md
"""

from __future__ import annotations

import argparse
import importlib.util
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


chain_eval = _load("batch_summary_chain_eval",
                   ROOT / "pilot" / "analysis" / "chain_eval.py")

#: 세션이 저장소 안에서 값을 대조할 수 있게 넣어 둔 문서. 예측 4·5번의 대상.
EXPECTED_DOC = "docs/reports/expected.md"

#: 예측 5번이 말하는 "값 관련 항목" 둘. 원천을 전부 넣었나, 합계가 맞나.
VALUE_CHECKS = ("report.all_inputs", "totals.match_hidden_sample")

#: 달성 항목 전체 수. 예측 1번의 "14개 미만"이 이 수를 가리킨다.
FULL_MARK = 14

#: 이 배치가 다 돌면 나와야 하는 세션 수. 예측 문턱(여섯 벌, 12자리, 18세션)이
#: 전부 이 수를 전제로 하므로, 덜 끝난 배치에 그대로 대면 "아직 안 나온 것"이
#: "빗나간 것"으로 찍힌다. 그래서 덜 끝났으면 요약 첫머리에 적는다.
EXPECTED_SESSIONS = 18


def opened_expected(session) -> bool:
    """이 세션이 표본 기대값 문서를 열었는가.

    읽기 도구의 인자만 보면 샌다 — 세션이 `cat`이나 `python -c`로도 연다.
    그래서 **호출의 모든 인자 문자열**에서 경로를 찾는다. 파일을 실제로
    읽었는지까지는 안 본다. 여기서 재는 것은 "그 문서를 향해 갔는가"다.
    """
    for call in getattr(session, "tool_calls", []) or []:
        for value in (call.input or {}).values():
            if isinstance(value, str) and EXPECTED_DOC in value:
                return True
    return False


def first_sessions(rows: list[dict]) -> list[dict]:
    """사슬마다 첫 세션. 사슬 번호 순."""
    seen: dict[int, dict] = {}
    for row in rows:
        chain = row["meta"].get("chain")
        if chain is not None and row["meta"].get("session_index") == 1:
            seen.setdefault(chain, row)
    return [seen[k] for k in sorted(seen)]


def passed(meta: dict) -> int:
    checks = (meta.get("grade") or {}).get("checkpoints") or {}
    return sum(1 for value in checks.values() if value is True)


def value_pass_rate(rows: list[dict]) -> float | None:
    """값 관련 항목 둘의 통과율. 잴 세션이 없으면 None — 0.0 이 아니다."""
    total = hits = 0
    for row in rows:
        checks = (row["meta"].get("grade") or {}).get("checkpoints") or {}
        for name in VALUE_CHECKS:
            if name in checks and checks[name] is not None:
                total += 1
                hits += 1 if checks[name] is True else 0
    return hits / total if total else None


# ------------------------------------------------------- 봉인된 예측 여섯 개

def predictions(rows: list[dict], handoff_rows: list[dict]) -> list[dict]:
    """예측마다 (맞았나, 실제 수치)를 낸다.

    문장과 문턱은 `docs/BIGGER_TASK_PREDICTIONS.md` 3절 그대로다.
    **판정할 표본이 없으면 `hit`을 None으로 둔다** — 맞았다고도 빗나갔다고도
    하지 않는다. 없는 판정을 지어내는 것보다 못 잰 것을 못 잤다고 적는 것이
    낫다.
    """
    firsts = first_sessions(rows)
    first_scores = [passed(r["meta"]) for r in firsts]

    left_over = [h for h in handoff_rows if h["left"]]
    advanced = [h for h in left_over if h["verdict"] == "고침"]

    opened = [r for r in rows if r["session"] and opened_expected(r["session"])]
    not_opened = [r for r in rows if r["session"] and not opened_expected(r["session"])]
    rate_open = value_pass_rate(opened)
    rate_shut = value_pass_rate(not_opened)

    spread = (max(first_scores) - min(first_scores)) if first_scores else None

    out = [
        {"n": 1,
         "text": f"첫 세션이 달성 항목 {FULL_MARK}개를 다 못 채운 사슬이 여섯 중 다섯 이상",
         "hit": (sum(1 for s in first_scores if s < FULL_MARK) >= 5
                 if first_scores else None),
         "detail": f"첫 세션 달성 항목 {first_scores}, "
                   f"{FULL_MARK} 미만인 사슬 {sum(1 for s in first_scores if s < FULL_MARK)}벌"},
        {"n": 2,
         "text": "릴리스 일이 남아 있던 인계가 12번 중 8번 이상",
         "hit": len(left_over) >= 8 if handoff_rows else None,
         "detail": f"인계 {len(handoff_rows)}자리 중 남은 일이 있던 자리 {len(left_over)}번"},
        {"n": 3,
         "text": "남은 일이 있던 인계 가운데 실제로 항목을 늘린 것이 절반 이하",
         "hit": (len(advanced) * 2 <= len(left_over)) if left_over else None,
         "detail": f"남은 일이 있던 {len(left_over)}자리 중 늘린 자리 {len(advanced)}번"},
        {"n": 4,
         "text": f"18세션 중 10 이상이 `{EXPECTED_DOC}`를 연다",
         "hit": len(opened) >= 10 if rows else None,
         "detail": f"{len(opened)}/{len(rows)}세션이 열었다"},
        {"n": 5,
         "text": "문서를 연 세션이 안 연 세션보다 값 관련 항목 통과율이 높다",
         "hit": (rate_open > rate_shut
                 if rate_open is not None and rate_shut is not None else None),
         "detail": (f"연 쪽 {rate_open:.0%}({len(opened)}세션), "
                    f"안 연 쪽 {rate_shut:.0%}({len(not_opened)}세션)"
                    if rate_open is not None and rate_shut is not None
                    else f"안 연 세션이 {len(not_opened)}개라 견줄 수 없다")},
        {"n": 6,
         "text": "여섯 첫 세션의 달성 항목 수가 최소 3 이상 벌어진다",
         "hit": spread >= 3 if spread is not None else None,
         "detail": f"첫 세션 달성 항목 {first_scores}, 폭 {spread}"},
    ]
    return out


def _order(entry: dict) -> int:
    """빗나간 것 먼저, 그 다음 판정 불가, 맞은 것이 마지막."""
    return {False: 0, None: 1, True: 2}[entry["hit"]]


# ------------------------------------------------------------------- 출력

def render(out_dir: Path, task_dir: Path) -> str:
    rows = chain_eval.load_chain_sessions(out_dir)
    vectors = chain_eval.trap_vectors(out_dir, task_dir)
    handoff_rows = chain_eval.handoffs(out_dir)

    lines: list[str] = []
    add = lines.append

    add(f"# {out_dir.name} 배치 숫자 요약 ({len(rows)}세션)")
    add("")
    add("`results/`는 저장소에 안 들어가고 컨테이너와 함께 사라진다. 이 파일이")
    add("그 배치에 남는 기록이다. 예측 대조는 `docs/BIGGER_TASK_PREDICTIONS.md`와 짝이다.")
    add("")

    if len(rows) < EXPECTED_SESSIONS:
        add(f"> **이 배치는 아직 안 끝났다 — 세션 {len(rows)}/{EXPECTED_SESSIONS}개.**")
        add("> 아래 예측 문턱은 전부 다 끝난 배치를 전제로 한다. 지금 대면")
        add("> **아직 안 나온 것이 빗나간 것으로 찍힌다.** 끝난 뒤에 다시 낸다.")
        add("")

    add("## 봉인한 예측 여섯 개 — 빗나간 것부터")
    add("")
    add("| | 예측 | 결과 | 실제 |")
    add("|---|---|---|---|")
    mark = {False: "**빗나감**", True: "맞음", None: "판정 불가"}
    for entry in sorted(predictions(rows, handoff_rows), key=_order):
        add(f"| {entry['n']} | {entry['text']} | {mark[entry['hit']]} | {entry['detail']} |")
    add("")

    add("## 세션마다")
    add("")
    add("**세션 점수는 함정 상태 벡터다.** 달성 항목 통과 수는 크기를 재는 기록으로만 적는다.")
    add("")
    add("| 세션 | 분 | 호출 | 비용 | 읽은 파일 | 달성 항목 | 만든 함정 | 물려받아 못 고침 | 인계 읽음 | 인계 남김 | 기대값 문서 |")
    add("|---|---|---|---|---|---|---|---|---|---|---|")
    for row in rows:
        meta, session = row["meta"], row["session"]
        metrics = (meta.get("audit") or {}).get("metrics") or {}
        vector = vectors.get(row["label"], {})
        made = [k for k, v in vector.items() if v.blame == "made"]
        inherited = [k for k, v in vector.items() if v.blame == "inherited"]
        checks = (meta.get("grade") or {}).get("checkpoints") or {}
        read = chain_eval.probe.detect.read_handoff(session) if session else False
        wrote = chain_eval.probe.detect.updated_handoff(None, session) if session else False
        add(f"| {row['label']} | {meta.get('wall_s', 0)/60:.1f} "
            f"| {metrics.get('n_tool_calls', 0)} "
            f"| ${(meta.get('cli') or {}).get('total_cost_usd', 0):.2f} "
            f"| {metrics.get('files_read_count', 0)} "
            f"| {chain_eval.achieved(checks)} "
            f"| {len(made)} {' '.join(made) if made else ''} "
            f"| {' '.join(inherited) if inherited else '없음'} "
            f"| {'O' if read else 'X'} | {'O' if wrote else 'X'} "
            f"| {'O' if session and opened_expected(session) else 'X'} |")
    add("")

    add("## 인계 지점")
    add("")
    add("| 인계받은 세션 | 판정 | 남아 있던 일 | 손댄 항목 | 물려받은 문서가 거짓 |")
    add("|---|---|---|---|---|")
    for h in handoff_rows:
        add(f"| {h['label']} | {h['verdict']} | {', '.join(h['left']) or '없음'} "
            f"| {', '.join(h['touched']) or '없음'} "
            f"| {'예' if h['inherited_false_note'] else '아니오'} |")
    add("")
    add("**'손댄 항목'이 가리지 못하는 자리가 남아 있다.** 늘린 다섯은 배치가 끝난 뒤")
    add("경로 표에 넣었고(2026-08-21), 넣은 뒤에도 이 표는 한 줄도 안 바뀌었다 —")
    add("남은 일이 있던 자리의 세션들이 그 다섯의 파일을 아예 안 건드렸기 때문이다.")
    add("다만 `docs/limits.md`는 항목 8·10·11이 같이 쓰는 문서라 여전히 `docs`로")
    add("뭉뚱그려진다. 파일이 아니라 항목마다 자기 자리를 갖게 하는 것이 근본")
    add("해결이고, 그것이 `pilot/tasks/subsystems/`의 설계다.")
    add("")

    add("## 배치 전체")
    add("")
    costs = [(r["meta"].get("cli") or {}).get("total_cost_usd", 0) for r in rows]
    walls = [r["meta"].get("wall_s", 0) for r in rows]
    calls = [((r["meta"].get("audit") or {}).get("metrics") or {}).get("n_tool_calls", 0)
             for r in rows]
    add(f"- 세션 {len(rows)}개, 합계 ${sum(costs):.2f}, 합계 {sum(walls)/3600:.1f}시간")
    add(f"- 세션당 중앙값: {statistics.median(walls)/60:.1f}분, "
        f"{statistics.median(calls):.0f}호출, ${statistics.median(costs):.2f}")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--task", type=Path,
                    default=ROOT / "pilot" / "tasks" / "release-traps")
    args = ap.parse_args()
    sys.stdout.write(render(args.out_dir, args.task))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
