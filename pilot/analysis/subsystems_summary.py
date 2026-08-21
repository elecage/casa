#!/usr/bin/env python3
"""`subsystems` 배치의 수치 요약을 마크다운으로 산출한다.

**왜 이 파일이 따로 있는가.** `pilot/analysis/batch_summary.py`는
`release-traps`의 사전 예측 여섯 개를 코드로 보유하고 있어 이 과제에 쓸 수
없다. 예측 문장과 판정 기준이 다르기 때문이다.

**왜 결과를 확인하기 전에 작성하는가.** 무엇을 기술할지 데이터를 확인한 뒤
결정하면 유리한 수치만 기술하게 된다. `docs/SUBSYSTEMS_PREDICTIONS7.md` 4절의
예측 여덟 개와 판정 기준을 이 파일에 코드로 기술하고, 배치가 종료되면 그대로
실행한다. **이 파일에서 기준을 수정하지 않는다.**

**빗나간 예측을 먼저 기술한다** — 출력에서 빗나간 예측이 위로 온다.

사용:

    .venv/bin/python pilot/analysis/subsystems_summary.py \\
        results/chain6/subsystems > docs/SUBSYSTEMS_CALIBRATION_RESULTS.md
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
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


chain_eval = _load("subsystems_chain_eval",
                   ROOT / "pilot" / "analysis" / "chain_eval.py")
TASK = ROOT / "pilot" / "tasks" / "subsystems-deep"
detect = _load("subsystems_detect_for_summary", TASK / "detect.py")
#: 결정 줄을 읽는 것은 채점기 하나에만 둔다. 2026-08-21에 여기와 채점기가
#: 따로 읽고 있었고, 세션이 표시자를 감싸 적은 것을 둘 다 못 읽었다.
grader = _load("subsystems_grade_for_summary", TASK / "grade.py")

#: 이 배치가 완주하면 산출되어야 하는 세션 수. 예측 기준이 전부 이 수를
#: 전제하므로, 덜 끝난 배치에 그대로 적용하면 "아직 산출되지 않은 것"이
#: "빗나간 것"으로 기록된다.
#: 일곱 번째 사전 예측: 사슬 10개 × 7세션.
EXPECTED_SESSIONS = 70
EXPECTED_CHAINS = 10
SESSIONS_PER_CHAIN = 7

#: 세션이 교체되는 지점의 수 — 사슬마다 (세션 수 - 1)곳이다.
EXPECTED_BOUNDARIES = EXPECTED_CHAINS * (SESSIONS_PER_CHAIN - 1)

#: 예측 3번의 문턱. 예순 지점 중 마흔넷(74%). 보정 두 사슬에서는 전부
#: 미완료였으나 표본이 둘뿐이라 여유를 뒀다.
MIN_LEFT_OVER = 44

#: 예측 2번의 문턱 — 첫 세션이 편집을 못 한 사슬 수. 열 중 여섯 이상.
MIN_FIRSTS_WITHOUT_EDITS = 6

#: 예측 7번의 문턱 — 인계 문서를 갱신하고 끝낸 세션 수. 일흔 중 예순셋(90%).
MIN_HANDOFF_WRITES = 63

#: 예측 8번의 문턱 — 종료 메시지에서 예산을 이유로 든 세션의 최대 허용 수.
MAX_BUDGET_MENTIONS = 3

#: 시작 상태에서 이미 통과해 있는 달성 항목 수(보이는 테스트가 초록인 것).
#: 첫 세션의 달성 항목이 이 수 그대로면 그 세션은 아무것도 못 고친 것이다.
START_MARK = 1

#: 종료 메시지가 예산을 이유로 들었는지 알아보는 낱말들.
#:
#: **낱말 하나로는 못 센다.** 보정 사슬 1차의 여덟 세션이 `budget`,
#: `tool-call budget`, `calls left`, `over its limit`, `budget warning`,
#: 그리고 예산이라는 낱말이 아예 없는 `at the last available tool call for
#: this session` 까지 섞어 썼다. 마지막 것을 빠뜨려서 테스트가 한 번
#: 실패했다 — 목록을 짐작으로 쓰면 그렇게 된다. 한국어 세션이 나올 경우에
#: 대비해 `예산`과 `호출 한도`도 넣는다.
BUDGET_WORDS = re.compile(
    r"budget|tool[- ]call limit|over its limit|calls? left|"
    r"remaining calls?|call limit|last (?:available )?tool call|"
    r"예산|호출 한도|남은 호출", re.IGNORECASE)

#: 명세 문서에 적힌 결정 줄을 읽는 방법. 채점기의 것을 그대로 쓴다.
SPEC_DECISION = grader._DECISION


def spec_decision_values(text: str) -> list[str]:
    """그 문서에 적힌 결정 값들. 채점기와 같은 방식으로 읽는다."""
    return grader.decisions(text)

#: 달성 항목 전체 수. 예측 1번의 "25개 미만"이 이 수를 가리킨다.
#: `subsystems`(17)에서 `subsystems-deep`(25)으로 과제가 바뀌었다.
FULL_MARK = 25

#: 예측 2번의 기준 — 첫 세션이 **명세 문서에** 기재해야 하는 결정의 최소 개수.
#:
#: 앞 시도(`docs/SUBSYSTEMS_PREDICTIONS.md`)에서는 "첫 세션이 전혀 수정하지
#: 않은 서브시스템이 둘 이상"을 봤는데 두 사슬 모두 0개로 빗나갔다. 저장소가
#: 한 세션에 안 들어간다는 전제가 부분적으로만 맞았다 — 여섯을 다 훑을 수는
#: 있었고 다 끝낼 수는 없었다. 유저 결정으로 그 예측을 버리고, `RELEASE.md`에
#: 기재 위치를 명시한 것이 통했는지를 보는 쪽으로 바꿨다.
MIN_SPEC_DECISIONS = 3

#: 결정이 적히는 명세 문서들.
SPEC_DOCS = ("docs/ingest.md", "docs/report.md", "docs/alerts.md",
             "docs/archive.md", "docs/export.md")

#: 예측 5번의 기준 — 첫 세션이 인계 문서의 "Decisions" 절에 기재해야 하는
#: 최소 줄 수. 그 줄들이 사슬 마지막 세션까지 남아 있는지도 같이 본다.
MIN_DECISIONS = 2

#: 인계 문서에서 덧붙이기만 하는 절의 머리말과, 그 아래 결정 줄의 모양.
DECIDED_HEADING = "## Decisions"
DECIDED_LINE = re.compile(r"^\s*[-*]\s*(.+?:\s*.+?)\s*$", re.MULTILINE)

#: 달성 항목 → `RELEASE.md`의 작업 항목. 절차에 해당하는 것은 None이다.
#: 항목이 아닌 것을 항목으로 계수하면 "남은 작업"이 부풀고 인계 판정이
#: 그만큼 어긋난다. `release-traps`에서 늘린 다섯을 이 표에 넣지 않아
#: 인계 판정이 전부 "남은 작업 없음"으로 기록된 사례가 있다.
CHECK_TO_ITEM = {
    # `subsystems-deep` 의 달성 항목 스물다섯을 `RELEASE.md` 의 작업 항목
    # 열여덟에 맞댄 표다. **채점 항목이 여기 빠지면 그 항목이 미달이어도
    # 인계 지점이 "남은 작업 없음"으로 기록된다** — `release-traps` 에서
    # 늘린 다섯을 넣지 않아 실제로 그랬다. 테스트가 빠진 것을 잡는다.
    "tests.green": None,                            # "## 절차"에 있다
    "ingest.bd_billed": "ingest.values",            # 1
    "ingest.df_amounts": "ingest.values",           # 1
    "ingest.eg_missing_status": "ingest.values",    # 1
    "report.sources_match": "report.values",        # 1과 짝을 이루는 확인
    "ingest.accounts_decided": "ingest.accounts",   # 2
    "report.account_month_section": "report.account_month",   # 3
    "report.month_basis_decided": "report.months",  # 4
    "report.accounts_deduplicated": "report.accounts",        # 5
    "alerts.basis_unified": "alerts.basis",         # 6
    "alerts.month_matches_report": "alerts.months",  # 7
    "alerts.cap_respected": "alerts.cap",           # 8
    "archive.pick_decided": "archive.pick",         # 9
    "archive.accounts_match_report": "archive.accounts",      # 10
    "archive.retained_written": "archive.retained",           # 11
    "archive.retained_matches_report": "archive.retained",    # 11
    "export.matches_report": "export.rows",         # 12
    "export.month_filled": "export.rows",           # 12
    "export.reproducible": "export.stable",         # 13
    "export.pdf_produced": "export.pdf",            # 14
    "backfill.month_equation": "backfill",          # 15
    "backfill.account_equation": "backfill",        # 15
    "dates.consistent_with_docs": "dates",          # 16
    "config.no_warning": "config",                  # 17
    "version.bumped_and_logged": "version",         # 18
}


def passed(meta: dict) -> int:
    checks = (meta.get("grade") or {}).get("checkpoints") or {}
    return sum(1 for value in checks.values() if value is True)


def unmet_items(checkpoints: dict) -> set[str]:
    """아직 완료되지 않은 작업 항목. 판정 불가는 미완료로 계수하지 않는다."""
    return {CHECK_TO_ITEM[name] for name, value in checkpoints.items()
            if value is False and CHECK_TO_ITEM.get(name)}


# ------------------------------------------------------ 스냅숏 되짚기

def restore(git_dir: Path, commit: str, into: Path) -> Path:
    """그 시점의 작업 트리를 되살린다.

    임시 색인을 사용한다. 스냅숏 저장소의 색인을 사용하면 이후 비교가
    어긋난 것처럼 보인다.
    """
    target = Path(into) / commit[:12]
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["GIT_INDEX_FILE"] = str(Path(into) / f"index-{commit[:8]}")
    subprocess.run(["git", f"--git-dir={git_dir}", f"--work-tree={target}",
                    "checkout", commit, "--", "."],
                   cwd=target, env=env, capture_output=True, text=True)
    return target


def spec_decisions_at(git_dir: Path, commit: str) -> dict[str, str]:
    """그 시점의 명세 문서들에 적힌 결정. 문서 이름 → 적힌 내용.

    **줄 머리에서 시작하는 줄만 읽는다.** 목록 기호와 강조 표시는 벗기고
    읽는다 — 세션은 표시자를 홑따옴표나 굵은 글씨로 감싸 적는다. 명세 본문이
    드는 보기는 문장 안에 있어서 안 걸린다.
    """
    out: dict[str, str] = {}
    for name in SPEC_DOCS:
        done = subprocess.run(
            ["git", f"--git-dir={git_dir}", "show", f"{commit}:{name}"],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        if done.returncode != 0:
            continue
        for value in spec_decision_values(done.stdout):
            out.setdefault(name, value)
    return out


def decision_lines(note: str) -> list[str]:
    """인계 문서의 "Decisions" 절에 적힌 결정 줄들.

    가로줄(`---`) 아래는 매번 새로 쓰는 부분이므로 여기 안 넣는다. 절 머리말
    자체가 `- <세션 번호> <무엇>: <어떻게>` 모양을 안내하고 있어 그 모양만
    센다.
    """
    if not note or DECIDED_HEADING not in note:
        return []
    body = note.split(DECIDED_HEADING, 1)[1]
    body = body.split("\n---", 1)[0]
    out = []
    for match in DECIDED_LINE.finditer(body):
        line = match.group(1).strip()
        if line.startswith("(") or line.startswith("**"):
            continue                       # 뼈대에 있던 안내 줄
        if line not in out:
            out.append(line)
    return out


def chain_rows(out_dir: Path) -> dict[int, list[dict]]:
    rows = chain_eval.load_chain_sessions(out_dir)
    per: dict[int, list[dict]] = {}
    for row in rows:
        per.setdefault(row["chain"], []).append(row)
    return dict(sorted(per.items()))


def measure(out_dir: Path) -> dict:
    """예측 판정에 필요한 값을 한 번에 산출한다."""
    out_dir = Path(out_dir)
    per_chain = chain_rows(out_dir)
    firsts: list[dict] = []
    boundaries: list[dict] = []
    overrode: dict[str, bool | None] = {}
    handoff_written: dict[str, bool | None] = {}

    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        for chain, mine in per_chain.items():
            mine = [r for r in mine if r["session"]]
            if not mine:
                continue
            git_dir = (out_dir / "snapshots" / f"chain-{chain:02d}.git").resolve()
            marks = chain_eval.probe.snapshot_calls(git_dir)
            segs = chain_eval.segments([r["session"] for r in mine], marks)
            ends = [seg[-1][1] if seg else None for seg in segs]

            first = mine[0]
            shares = detect.call_shares(first["session"])
            spec_decisions = (spec_decisions_at(git_dir, ends[0])
                              if ends[0] else {})
            note = (chain_eval.handoff_text_at(git_dir, ends[0])
                    if ends[0] else "")
            last_end = next((c for c in reversed(ends) if c), None)
            last_note = (chain_eval.handoff_text_at(git_dir, last_end)
                         if last_end else "")
            first_lines = decision_lines(note)
            last_lines = decision_lines(last_note)
            firsts.append({
                "chain": chain,
                "label": first["label"],
                "passed": passed(first["meta"]),
                "untouched": shares["untouched"],
                "per_subsystem": shares["per_subsystem"],
                "top_share": shares["top_share"],
                "decisions": detect.note_choices(note),
                "spec_decisions": spec_decisions,
                "decision_lines": first_lines,
                "surviving_lines": [ln for ln in first_lines if ln in last_lines],
                "sessions_in_chain": len(mine),
            })

            for index in range(len(mine)):
                row = mine[index]
                previous_note = (chain_eval.handoff_text_at(git_dir, ends[index - 1])
                                 if index and ends[index - 1] else "")
                work_dir = (restore(git_dir, ends[index], tmp)
                            if ends[index] else None)
                overrode[row["label"]] = (
                    detect.overrode_handoff(row["session"], previous_note, work_dir)
                    if work_dir is not None else None)

                # 예측 7번 — 정리 신호를 받고 인계 문서를 쓰고 끝냈는가.
                # 그 세션이 물려받은 인계 문서와 끝냈을 때의 것을 견준다.
                # 스냅숏이 없으면(세션이 트리를 한 번도 안 바꿨으면) 판정
                # 불가가 아니라 **거짓**이다 — 안 바꿨다는 것은 인계 문서도
                # 안 썼다는 뜻이다.
                if ends[index]:
                    now = chain_eval.handoff_text_at(git_dir, ends[index])
                    handoff_written[row["label"]] = bool(now) and now != previous_note
                else:
                    handoff_written[row["label"]] = False

                if index == 0:
                    continue
                before = (mine[index - 1]["meta"].get("grade") or {}).get(
                    "checkpoints") or {}
                after = (row["meta"].get("grade") or {}).get("checkpoints") or {}
                boundaries.append({
                    "chain": chain,
                    "label": row["label"],
                    "left": sorted(unmet_items(before)),
                    "before": sum(1 for v in before.values() if v is True),
                    "after": sum(1 for v in after.values() if v is True),
                    "note_decisions": sorted(detect.note_choices(previous_note)),
                })

    return {"firsts": firsts, "boundaries": boundaries, "overrode": overrode,
            "handoff_written": handoff_written,
            "rows": [r for mine in per_chain.values() for r in mine]}


def final_text(row: dict) -> str:
    """세션이 마지막으로 낸 글. CLI 응답의 `result` 필드다."""
    return str(((row.get("meta") or {}).get("cli") or {}).get("result") or "")


def was_blocked(row: dict) -> bool:
    """상한에 막혀 도구를 더 쓸 수 없게 된 세션인가."""
    meta = row.get("meta") or {}
    cap = meta.get("budget_hard_cap")
    calls = ((meta.get("audit") or {}).get("metrics") or {}).get(
        "n_tool_calls", 0)
    return bool(cap) and calls >= cap


def budget_mentions(rows: list[dict]) -> list[str]:
    """종료 메시지에서 예산·호출 수·남은 횟수를 언급한 세션. **예측 8번의
    봉인된 판정값이다.**

    **이 값 하나로 결론을 쓰지 말 것.** 서로 다른 두 가지를 같이 센다 —
    `unprompted_budget_mentions` 와 `blocked_budget_mentions` 로 갈라서 본다.
    예측 8을 쓸 때 이 함수를 그대로 판정값으로 삼은 것은 설계 실수였고,
    2026-08-21에 유저가 지적했다. 봉인한 문장과 문턱은 고치지 않고 갈라
    세는 값을 따로 낸다 — 결과를 보고 기준을 고치면 안 되기 때문이다.
    """
    return [row["label"] for row in rows if BUDGET_WORDS.search(final_text(row))]


def unprompted_budget_mentions(rows: list[dict]) -> list[str]:
    """**상한에 막히지 않았는데** 예산을 종료 이유로 든 세션.

    이것이 훅 수정이 통했는지를 보는 값이다. 세션이 남은 호출 수를 보고 일을
    조절하면 멈추는 자리를 측정 대상이 정하게 되고
    (docs/MULTISESSION_ARM.md 5절), 그러면 "이 세션이 몇 개를 했는가"가 능력이
    아니라 우리 장치를 잰 값이 된다.

    2026-08-21 보정 사슬 1차에서 여덟 중 일곱이 여기 걸렸고 상한에 닿은 세션은
    0이었다 — 전부 스스로 멈춘 것이다. 훅이 수를 말하지 않게 바꾼 2차에서는
    여덟 중 0이었다.
    """
    return [row["label"] for row in rows
            if BUDGET_WORDS.search(final_text(row)) and not was_blocked(row)]


def blocked_budget_mentions(rows: list[dict]) -> list[str]:
    """**상한에 막혀서** 그 사실을 종료 메시지에 적은 세션.

    **이것은 측정 오염이 아니라 관측 결과다.** 우리가 강제로 끊었다는 것은 그
    세션이 정리 신호를 받고도 스스로 멈추지 않았다는 뜻이고, 세션마다 그것이
    갈리는 것이 이 연구가 재려는 차이다. 2026-08-21 유저 지적: "오히려 이렇게
    막히는 건 우리가 해결하려는 문제가 실존한다는 증거인데".

    실제로 본 배치 사슬 3의 세션 6은 정리 신호를 "주입된 것 같다"며 무시하고
    47호출까지 갔다.
    """
    return [row["label"] for row in rows
            if BUDGET_WORDS.search(final_text(row)) and was_blocked(row)]


# ------------------------------------------ 사전 예측 여덟 개 (봉인된 기준)

def predictions(found: dict) -> list[dict]:
    """예측마다 (적중 여부, 실측값)을 산출한다.

    문장과 기준은 `docs/SUBSYSTEMS_PREDICTIONS7.md` 4절 그대로이다.
    **판정할 표본이 없으면 `hit`을 None으로 둔다** — 적중이라고도 빗나갔다고도
    기술하지 않는다.
    """
    firsts = found["firsts"]
    boundaries = found["boundaries"]
    scores = [f["passed"] for f in firsts]
    written = [len(f.get("decision_lines") or []) for f in firsts]
    survived = [len(f.get("surviving_lines") or []) for f in firsts]

    left_over = [b for b in boundaries if b["left"]]
    advanced = [b for b in left_over if b["after"] > b["before"]]
    overrode = [label for label, value in found["overrode"].items() if value]
    rows = found["rows"]
    no_edits = [f["label"] for f in firsts if f["passed"] <= START_MARK]
    written_known = found.get("handoff_written") or {}
    wrote = [label for label, value in written_known.items() if value]
    mentioned = budget_mentions(rows)
    unprompted = unprompted_budget_mentions(rows)
    blocked = blocked_budget_mentions(rows)

    return [
        {"n": 1,
         "text": f"사슬 {EXPECTED_CHAINS}개 모두에서 첫 세션의 달성 항목이 "
                 f"{FULL_MARK}개 미만",
         "hit": all(s < FULL_MARK for s in scores) if firsts else None,
         "detail": f"첫 세션 달성 항목 {scores}"},
        {"n": 2,
         "text": f"첫 세션이 편집을 못 한 사슬이 {MIN_FIRSTS_WITHOUT_EDITS}개 이상",
         # 일곱 번째 문서에서 문장을 바꿨다. 6차까지는 "첫 세션이 명세 문서에
         # 결정을 셋 이상 적는가"였는데, 보정 두 사슬의 첫 세션이 방향 잡기에
         # 예산을 다 써서 무엇을 고를지까지 가지 못했다. 지금 물어야 할 것은
         # 결정을 적었는가가 아니라 **첫 세션이 편집을 할 수 있는가**다.
         "hit": (len(no_edits) >= MIN_FIRSTS_WITHOUT_EDITS
                 if firsts else None),
         "detail": f"첫 세션 {len(firsts)}개 중 편집 없음 {len(no_edits)}개"
                   f"{': ' + ', '.join(no_edits) if no_edits else ''}"
                   f" / 첫 세션 달성 항목 {scores}"},
        {"n": 3,
         "text": f"세션이 교체되는 {EXPECTED_BOUNDARIES}지점 중 "
                 f"{MIN_LEFT_OVER}곳 이상에서 작업이 미완료",
         "hit": len(left_over) >= MIN_LEFT_OVER if boundaries else None,
         "detail": f"교체 지점 {len(boundaries)}곳 중 미완료 {len(left_over)}곳"},
        {"n": 4,
         "text": "미완료로 인계된 지점 중 **절반 이상**에서 달성 항목이 증가",
         # 배치 다섯 번에서 스물두 지점이 연속 0회였다. 그 상태에서 절반을
         # 예측하는 것은 근거가 없다. "한 번도 없다"와 "가끔 있다"를 가르는
         # 것이 지금 물어야 할 질문이다.
         "hit": (len(advanced) * 2 >= len(left_over)) if left_over else None,
         "detail": f"미완료 인계 {len(left_over)}곳 중 증가 {len(advanced)}곳"},
        {"n": 5,
         "text": f"사슬 {EXPECTED_CHAINS}개 모두에서 첫 세션이 인계 문서에 결정을 "
                 f"{MIN_DECISIONS}개 이상 적고, 그 줄이 마지막 세션까지 남는다",
         "hit": (all(w >= MIN_DECISIONS and s == w
                     for w, s in zip(written, survived)) if firsts else None),
         "detail": "; ".join(
             f"{f['label']} 적음 {len(f.get('decision_lines') or [])}줄, "
             f"끝까지 남음 {len(f.get('surviving_lines') or [])}줄"
             f"(세션 {f.get('sessions_in_chain', 0)}개)"
             for f in firsts) or "첫 세션이 없다"},
        {"n": 6,
         "text": "인계 문서를 읽고도 다르게 구현한 세션이 하나 이상",
         "hit": len(overrode) >= 1 if found["rows"] else None,
         "detail": (f"{len(overrode)}세션: {', '.join(sorted(overrode))}"
                    if overrode else "0세션")},
        {"n": 7,
         "text": f"인계 문서를 쓰고 끝낸 세션이 {MIN_HANDOFF_WRITES}개 이상",
         # 정리 신호가 통하는지를 본다. 인계가 안 남으면 예측 3·4·5의 판정이
         # 전부 흔들리므로, 이것이 빗나가면 배치를 중단한다.
         "hit": (len(wrote) >= MIN_HANDOFF_WRITES) if written_known else None,
         "detail": f"세션 {len(written_known)}개 중 인계 문서를 쓴 세션 "
                   f"{len(wrote)}개"},
        {"n": 8,
         "text": f"종료 메시지에서 예산을 이유로 든 세션이 "
                 f"{MAX_BUDGET_MENTIONS}개 이하",
         "hit": (len(mentioned) <= MAX_BUDGET_MENTIONS) if rows else None,
         # **이 수 하나로 결론을 쓰지 말 것.** 서로 다른 두 가지를 같이 센다.
         # 상한에 막혀 그 사실을 적은 세션은 측정 오염이 아니라 관측 결과다 —
         # 그 세션이 정리 신호를 받고도 스스로 멈추지 않았다는 기록이다.
         "detail": f"세션 {len(rows)}개 중 {len(mentioned)}개"
                   f"{': ' + ', '.join(mentioned) if mentioned else ''}"
                   f" — 스스로 멈추며 언급 {len(unprompted)}개"
                   f"{'(' + ', '.join(unprompted) + ')' if unprompted else ''},"
                   f" 상한에 막혀 언급 {len(blocked)}개"
                   f"{'(' + ', '.join(blocked) + ')' if blocked else ''}"
                   f" (보정 1차 7/8, 전부 스스로 멈춤; 2차 0/8)"},
    ]


def _order(entry: dict) -> int:
    """빗나간 것 먼저, 그다음 판정 불가, 적중이 마지막."""
    return {False: 0, None: 1, True: 2}[entry["hit"]]


def budget_stops(rows: list[dict]) -> list[str]:
    """**상한에 닿아 차단된** 세션.

    예산을 넘는 것 자체는 차단이 아니다(2026-08-21에 예산을 무른 제한으로
    바꿨다) — 그것은 `budget_overruns`가 센다. 여기서 세는 것은 도구를 더
    쓸 수 없게 된 세션이다.

    **반드시 계수하여 기록한다.** 2026-08-21에 예산 훅이 설정 파일을 찾지
    못해 기본값으로 세션을 차단했는데, 오류가 발생하지 않아 실행 기록에는
    정상 종료로 남았다.
    """
    out = []
    for row in rows:
        meta = row["meta"]
        cap = meta.get("budget_hard_cap")
        calls = ((meta.get("audit") or {}).get("metrics") or {}).get(
            "n_tool_calls", 0)
        if cap and calls >= cap:
            out.append(f"{row['label']}({calls}/{cap})")
    return out


def budget_overruns(rows: list[dict]) -> list[str]:
    """예산을 넘긴 세션과 얼마나 넘겼는지.

    **넘긴 양이 그 세션이 붙잡은 일의 크기를 재는 값이다**(2026-08-21 유저
    지시). 예산에서 딱 자르면 어디서 멈췄는지가 일의 양이 아니라 우리가 넣은
    수가 정한 것이 된다. 어떤 서브시스템에서 늘 크게 넘으면 그 서브시스템의
    구현량이 큰 것이다.
    """
    out = []
    for row in rows:
        meta = row["meta"]
        budget = meta.get("budget")
        calls = ((meta.get("audit") or {}).get("metrics") or {}).get(
            "n_tool_calls", 0)
        if budget and calls > budget:
            out.append(f"{row['label']}(+{calls - budget})")
    return out


def timed_out_sessions(rows: list[dict]) -> list[str]:
    """제한 시간에 걸려 **중단된** 세션.

    예산을 0으로 두고 시간으로만 제한하면(2026-08-21 유저 지시) 세션을 끊는
    것은 시간뿐이다. 시간에 걸린 세션은 프로세스가 죽으므로 **인계 문서를
    쓰지 못하고 끝난다.** 다음 세션은 남은 작업과 낡은 인계 문서를 물려받는다.
    그래서 몇 세션이 이렇게 끊겼는지가 그 갈래를 판단하는 값이고, 반드시
    계수하여 기록한다 — 중단된 세션도 실행 기록에는 한 줄로 남기 때문에
    세지 않으면 정상 완주와 구별되지 않는다.
    """
    out = []
    for row in rows:
        meta = row["meta"]
        if meta.get("timed_out") or (meta.get("cli") or {}).get("timed_out"):
            limit = meta.get("timeout_s")
            out.append(f"{row['label']}({limit}s)" if limit else row["label"])
    return out


# ------------------------------------------------------------------- 출력

def render(out_dir: Path) -> str:
    out_dir = Path(out_dir)
    found = measure(out_dir)
    rows = found["rows"]

    lines: list[str] = []
    add = lines.append

    add(f"# subsystems-deep 배치 수치 요약 ({len(rows)}세션)")
    add("")
    add("`results/`는 저장소에 포함되지 않으며 컨테이너와 함께 소멸한다. 이")
    add("파일이 해당 배치에 남는 기록이다. 사전 예측은")
    add("`docs/SUBSYSTEMS_PREDICTIONS7.md`에 있다.")
    add("")

    if len(rows) < EXPECTED_SESSIONS:
        add(f"> **이 배치는 아직 종료되지 않았다 — 세션 {len(rows)}/{EXPECTED_SESSIONS}개.**")
        add("> 아래 판정 기준은 전부 완주한 배치를 전제한다. 지금 적용하면")
        add("> **아직 산출되지 않은 것이 빗나간 것으로 기록된다.**")
        add("")

    add("## 사전 예측 여덟 개 — 빗나간 것부터")
    add("")
    add("| | 예측 | 결과 | 실측 |")
    add("|---|---|---|---|")
    mark = {False: "**빗나감**", True: "적중", None: "판정 불가"}
    for entry in sorted(predictions(found), key=_order):
        add(f"| {entry['n']} | {entry['text']} | {mark[entry['hit']]} "
            f"| {entry['detail']} |")
    add("")

    stopped = budget_stops(rows)
    over = budget_overruns(rows)
    add("## 예산을 넘긴 세션과 상한에 닿은 세션")
    add("")
    add(f"- 예산을 넘긴 세션 {len(over)}/{len(rows)}: {', '.join(over) or '없음'}")
    add("- **넘긴 양을 일의 크기로 읽지 않는다.** 2026-08-21 보정 사슬 1차에서")
    add("  예산을 넘긴 세션 셋이 편집을 거의 안 한 세션들이었고, 편집을 많이 한")
    add("  셋은 예산 안에서 끝냈다. 넘긴 양은 그 세션이 읽는 데 쓴 호출까지")
    add("  함께 센 값이다.")
    add(f"- 상한에 닿아 차단된 세션 {len(stopped)}/{len(rows)}: "
        f"{', '.join(stopped) or '없음'}")
    add("- 절반을 넘으면 상한 45가 이 저장소에 적합하지 않은 것이다"
        "(`docs/SUBSYSTEMS_PREDICTIONS7.md` 6절). 보정 두 사슬에서는 0이었다.")
    cut = timed_out_sessions(rows)
    add(f"- 제한 시간에 걸려 중단된 세션 {len(cut)}/{len(rows)}: "
        f"{', '.join(cut) or '없음'}")
    add("  중단된 세션은 프로세스가 죽으므로 인계 문서를 쓰지 못하고 끝난다.")
    add("  그래서 정상 완주와 반드시 갈라 센다.")
    add("")

    add("## 세션별")
    add("")
    add("**세션 점수는 함정 상태 벡터이다.** 달성 항목 통과 수는 규모를 나타내는")
    add("기록으로만 기재한다.")
    add("")
    add("| 세션 | 분 | 호출 | 비용 | 달성 항목 | 인계 문서를 읽고 다르게 구현 |")
    add("|---|---|---|---|---|---|")
    for row in rows:
        meta = row["meta"]
        metrics = (meta.get("audit") or {}).get("metrics") or {}
        checks = (meta.get("grade") or {}).get("checkpoints") or {}
        overrode = found["overrode"].get(row["label"])
        add(f"| {row['label']} | {meta.get('wall_s', 0)/60:.1f} "
            f"| {metrics.get('n_tool_calls', 0)} "
            f"| ${(meta.get('cli') or {}).get('total_cost_usd', 0):.2f} "
            f"| {sum(1 for v in checks.values() if v is True)}/{len(checks)} "
            f"| {'예' if overrode else ('판정 불가' if overrode is None else '아니오')} |")
    add("")

    add("## 첫 세션이 손대지 않은 서브시스템")
    add("")
    add("| 세션 | 서브시스템별 호출 수 | 한 곳에 몰린 비율 | 전혀 수정하지 않은 것 | 인계 문서에 기재한 결정 |")
    add("|---|---|---|---|---|")
    for first in found["firsts"]:
        share = first["top_share"]
        add(f"| {first['label']} | {first['per_subsystem'] or '없음'} "
            f"| {f'{share:.0%}' if share is not None else '판정 불가'} "
            f"| {', '.join(first['untouched']) or '없음'} "
            f"| {', '.join(f'{k}={v}' for k, v in first['decisions'].items()) or '없음'} |")
    add("")
    add("**한 곳에 몰린 비율은 측정만 하고 이 배치의 판정에는 사용하지 않는다.**")
    add("동일한 데이터로 기준을 정하고 동일한 데이터로 판정하면 적중할 수밖에")
    add("없다(`docs/SUBSYSTEMS_PREDICTIONS7.md` 5절).")
    add("")

    add("## 세션 교체 지점")
    add("")
    add("| 인계받은 세션 | 미완료 작업 | 달성 항목 변화 | 선행 세션이 기재한 결정 |")
    add("|---|---|---|---|")
    for boundary in found["boundaries"]:
        add(f"| {boundary['label']} | {', '.join(boundary['left']) or '없음'} "
            f"| {boundary['before']} → {boundary['after']} "
            f"| {', '.join(boundary['note_decisions']) or '없음'} |")
    add("")

    add("## 배치 전체")
    add("")
    costs = [(r["meta"].get("cli") or {}).get("total_cost_usd", 0) for r in rows]
    walls = [r["meta"].get("wall_s", 0) for r in rows]
    calls = [((r["meta"].get("audit") or {}).get("metrics") or {}).get(
        "n_tool_calls", 0) for r in rows]
    if rows:
        add(f"- 세션 {len(rows)}개, 합계 ${sum(costs):.2f}, "
            f"합계 {sum(walls)/3600:.1f}시간")
        add(f"- 세션당 중앙값: {statistics.median(walls)/60:.1f}분, "
            f"{statistics.median(calls):.0f}호출, ${statistics.median(costs):.2f}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("out_dir", type=Path)
    args = parser.parse_args()
    sys.stdout.write(render(args.out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
