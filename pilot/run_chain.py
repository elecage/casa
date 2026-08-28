#!/usr/bin/env python3
"""Run a project as a chain of sessions (docs/MULTISESSION_ARM.md).

Difference from `run_sessions.py`, which runs independent sessions of one
task: here the sessions of a chain share one working directory. Session 2
starts from whatever session 1 left behind — the repo, the commits, and any
handoff note. That is the whole point: the phenomenon under study is what
happens *between* sessions, and a design with one session per task cannot
show it.

Three things this adds:

  workdir inheritance   the chain's directory is prepared once, at session 1
  a session budget      enforced by pilot/chain_budget.py as a PreToolUse
                        hook, because the CLI has no turn cap and because
                        where a session stops must not be chosen by the thing
                        being measured
  grading at every seam the task grader runs after each session, and the
                        result is written to disk but never shown to the
                        agent — a session must not learn its score

Chains are isolated from each other the same way independent sessions were:
separate directory, separate git repo, separate transcript project dir.
Inside a chain the sessions are deliberately dependent, so the unit of
analysis is the chain, not the session.

Usage:
    python pilot/run_chain.py pilot/tasks/casefile --chains 3 --sessions 6 \\
        --budget 60 --out results/chain/casefile
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from casa.audit import audit_session  # noqa: E402
from casa.rules import load_rules  # noqa: E402
import chain_budget  # noqa: E402
import cut_hook  # noqa: E402
import queue_hook  # noqa: E402
import snapshot  # noqa: E402
from queue_grade import technical_outcome  # noqa: E402
from run_sessions import (  # noqa: E402
    check_auth, prepare_workdir, rules_for, run_headless,
    session_never_started, transcript_dir_for,
)

HOOK = Path(__file__).resolve().parent / "chain_budget.py"

#: 호출 총량으로 돌릴 때의 세션 수 안전판. 끊는 조건에서는 세션이 10호출 만에
#: 끝나므로 총량이 다 되기까지 세션이 여럿 필요하다. 무한히 돌지는 않게 한다.
MAX_SESSIONS_PER_CHAIN = 40
SNAPSHOT_DIR_NAME = "snapshots"
CONFIG_NAME = ".casa-chain.json"


def install_budget(workdir: Path, budget: int, warn_margin: int = 5) -> None:
    """예산 훅 배선. 구현은 `pilot/chain_budget.py` 에 있다 — 단발 러너도
    같은 것을 쓴다."""
    chain_budget.install(workdir, budget, warn_margin)


def calls_of(row: dict) -> int:
    """그 세션이 실제로 쓴 도구 호출 수."""
    return ((row.get("audit") or {}).get("metrics") or {}).get(
        "n_tool_calls", 0)


def earlier_rows(out_dir: Path, chain: int) -> list[dict]:
    """이어서 진행할 때 앞서 끝난 세션 기록들. 쓴 호출 수를 이어 세기 위해서."""
    out = []
    for path in sorted(Path(out_dir).glob(f"session-c{chain:02d}s*.json")):
        try:
            out.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return out


def trailing_cut_streak(rows: list[dict]) -> int:
    """재개할 때 이어받을 연속 끊기 횟수. 뒤에서부터 끊긴 세션을 센다.

    **0에서 다시 시작하면 안 된다.** 직전 세션들이 연달아 끊긴 채로 배치가
    중단됐다면, 0에서 다시 세는 순간 상한을 넘겨 끊을 수 있다.

    2026-08-22 배치에서 실제로 그 자리에 있었다. 사슬 8이 끊긴 세션
    (`c08s12`, 연속 1)으로 끝난 채 외부에서 종료됐고, 그대로 이어 실행했다면
    세 세션이 연달아 끊길 수 있었다. 그 사슬은 끊기의 손익이 아니라 우리가
    사슬에 일할 기회를 주지 않은 것을 보여 주게 된다.
    """
    streak = 0
    for row in reversed(rows):
        if not row.get("cut"):
            break
        streak += 1
    return streak


def progress_of(result: dict) -> int | None:
    """그 시점에 채워진 완료 조건 수. 못 읽으면 None.

    **과제마다 채점기 출력의 열쇠가 다르다** — 옛 과제들은 `milestone_score`,
    큐 과제 셋(`pilot/queue_grade.py`)은 `met` 이다. 사슬 요약이 진척을 세려면
    둘 다 읽어야 한다.

    **이 수는 점수가 아니라 부수 기록이다**(`pilot/tasks/queue-flat/DESIGN.md`
    8절). 세션 점수는 관측 대상의 상태 벡터다.
    """
    for key in ("milestone_score", "met"):
        value = (result or {}).get(key)
        if isinstance(value, int):
            return value
    return None


def progress_line(result: dict) -> str:
    """실행 중에 한 줄로 보여 주는 진행 표시."""
    result = result or {}
    if isinstance(result.get("milestone_score"), int):
        return (f"마일스톤 {result['milestone_score']}  "
                f"위반 {result.get('violations')}")
    if isinstance(result.get("met"), int):
        claimed = len(result.get("claimed_not_met") or [])
        return (f"충족 {result['met']}/{result.get('total')}  "
                f"적었는데 안 된 항목 {claimed}")
    return "채점 결과 없음"


def grade(task_dir: Path, workdir: Path) -> dict:
    """Score the chain's current state. Never shown to the session."""
    try:
        done = subprocess.run(
            [sys.executable, str(task_dir / "grade.py"), str(workdir)],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=600)
        return json.loads(done.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, TypeError,
            OSError) as exc:
        # A session's own program can emit bytes that are not UTF-8; without
        # errors="replace" the reader thread dies and stdout comes back None,
        # which killed a whole chain mid-run. One ungradeable session must
        # never take the chain with it.
        return {"parse_error": True, "detail": str(exc)[:300]}


def collect_transcript(workdir: Path, cli: dict, out_dir: Path,
                       label: str, seen: set[str]) -> Path | None:
    """Copy this session's transcript out of the shared project directory.

    Chained sessions write into the same directory, so a transcript already
    claimed by an earlier session must not be picked up again.
    """
    tdir = transcript_dir_for(workdir)
    session_id = cli.get("session_id")
    candidate = tdir / f"{session_id}.jsonl" if session_id else None
    if candidate is None or not candidate.exists():
        if not tdir.exists():
            return None
        fresh = [p for p in tdir.glob("*.jsonl") if p.name not in seen]
        if not fresh:
            return None
        candidate = max(fresh, key=lambda p: p.stat().st_mtime)
    seen.add(candidate.name)
    saved = out_dir / f"transcript-{label}.jsonl"
    shutil.copyfile(candidate, saved)
    return saved


def completed_sessions(out_dir: Path, chain: int) -> int:
    """How far this chain already got, for resuming an interrupted batch.

    A chain is expensive and the usage window is finite; losing six sessions
    because the batch stopped at the fifth would be worse than the risk of
    continuing into a slightly odd state.
    """
    index = 0
    while (out_dir / f"session-c{chain:02d}s{index + 1:02d}.json").exists():
        index += 1
    return index


#: 둘째 세션부터 주는 프롬프트. 없으면 첫 세션 것을 그대로 쓴다.
FOLLOWUP_PROMPT = "prompt_followup.txt"


def load_prompts(task_dir: Path) -> tuple[str, str]:
    """(첫 세션 프롬프트, 후속 세션 프롬프트).

    **왜 갈라 주는가.** 사슬의 둘째 세션부터는 앞사람이 하던 일을 이어받는
    자리인데, 지금까지는 다섯 세션이 전부 "릴리스를 준비해라"라는 같은 말을
    받았다. 실제로 새 세션을 여는 사람은 "어제 하던 거 이어서" 라고 말한다.
    그 차이가 세션의 행동을 바꾸므로 조건에서 맞춰 준다.

    **프롬프트로 역량을 조절하는 것이 아니다**(`harness/anchor.md`). 실제
    사용자가 쓸 법한 말에 맞추는 것이고, 일하는 요령은 넣지 않는다.

    후속 프롬프트 파일이 없는 과제는 첫 세션 것을 그대로 쓴다 — 사슬이 아닌
    과제와 옛 과제 11종이 그렇다.
    """
    first = (task_dir / "prompt.txt").read_text(encoding="utf-8")
    followup = task_dir / FOLLOWUP_PROMPT
    if followup.is_file():
        return first, followup.read_text(encoding="utf-8")
    return first, first


def run_chain(task_dir: Path, out_dir: Path, chain: int, sessions: int,
              budget: int, model: str | None, timeout_s: int,
              resume: bool = False, cut_at: int = 0,
              allowance: int = 0, max_cut_streak: int = 0) -> list[dict]:
    first_prompt, next_prompt = load_prompts(task_dir)
    relevant = [ln.strip() for ln in
                (task_dir / "relevant_files.txt").read_text(
                    encoding="utf-8").splitlines() if ln.strip()]
    # **규칙을 세션에게 말하지 않는 과제에는 캐너리 규칙을 적용하지 않는다**
    # (`pilot/run_sessions.py` 의 `rules_for`). `queue-flat` 이 그런 과제다.
    rules_path = rules_for(task_dir)
    rules = load_rules(rules_path) if rules_path else None

    workdir = out_dir / f"chain-{chain:02d}"
    done = completed_sessions(out_dir, chain) if resume else 0
    if done and workdir.exists():
        print(f"  이어서 진행: 세션 {done}개 완료됨")
    else:
        # Prepared once, at session 1. Preparing it again would wipe the
        # previous session's work, which is the one thing a chain must keep.
        done = 0
        workdir = prepare_workdir(task_dir, workdir)
    install_budget(workdir, budget)
    # **예산 훅 다음에 배선한다.** 예산 훅이 PreToolUse 목록을 통째로 쓰므로
    # 순서가 뒤집히면 끊는 장치가 조용히 사라지고, 두 조건이 같아진 채로
    # 배치가 돈다.
    cut_hook.install(workdir, cut_at, max_streak=max_cut_streak)
    # 큐 과제는 `NEXT.md` 가 시작 상태의 일부다. **스냅숏 훅보다 먼저 만든다** —
    # 그쪽이 세션 시작 전 상태를 커밋 하나로 찍어 두기 때문이다.
    is_queue_task = (task_dir / "queue.json").is_file()
    if is_queue_task:
        queue_hook.prepare(workdir, task_dir.name)
    # 예산 훅 다음에 배선한다 — settings.json 을 덮지 않고 합친다.
    snapshot.install(workdir, out_dir / SNAPSHOT_DIR_NAME /
                     f"chain-{chain:02d}.git")
    # 갱신 훅은 스냅숏 훅 **다음에** 배선한다 — 그쪽이 `PostToolUse` 목록을
    # 통째로 쓰고, 이쪽은 맨 앞에 끼워 넣어 갱신된 `NEXT.md` 가 이번 호출의
    # 스냅숏에 담기게 한다.
    if is_queue_task:
        queue_hook.install(workdir, task_dir.name)

    seen: set[str] = set()
    rows: list[dict] = []
    # 재개할 때는 앞 세션들의 끝자락에서 연속 끊기 횟수를 이어받는다.
    # 0으로 시작하면 상한을 넘겨 끊게 된다 — `trailing_cut_streak` 참조.
    earlier = earlier_rows(out_dir, chain) if done else []
    cut_streak = trailing_cut_streak(earlier)
    used = sum(calls_of(r) for r in earlier)
    index = done
    while True:
        index += 1
        # **끝나는 조건이 둘이다.** 호출 총량을 주면 그것이 다 될 때까지
        # 돌린다 — 끊는 조건과 안 끊는 조건에서 세션 수가 아니라 **쓴 호출
        # 수**를 같게 맞추기 위해서다(2026-08-22 유저 지적). 총량을 안 주면
        # 예전처럼 세션 수로 끝낸다.
        if allowance:
            if used >= allowance or index > MAX_SESSIONS_PER_CHAIN:
                break
        elif index > sessions:
            break
        label = f"c{chain:02d}s{index:02d}"
        # **연속으로 끊은 횟수를 세션마다 새로 써 준다.** 상한에 닿으면 훅이
        # 이번 세션은 신호가 켜져도 안 끊는다 — 안 그러면 사슬이 토막만
        # 만들면서 호출 총량을 태우고, 그 결과는 끊기의 손익이 아니라 우리가
        # 사슬을 굶긴 것을 보여 준다(2026-08-22 유저 지적).
        cut_hook.install(workdir, cut_at, streak=cut_streak,
                         max_streak=max_cut_streak)
        marks_before = cut_hook.cut_marks(workdir.parent)
        started = time.time()
        cli = run_headless(workdir, first_prompt if index == 1 else next_prompt,
                           model, timeout_s)
        # 마지막 한 번 — 세션의 끝 편집을 훅이 못 잡고 끝나는 수가 있다.
        snapshot.take(workdir)
        row: dict = {
            "task": task_dir.name, "chain": chain, "session_index": index,
            "label": label, "wall_s": round(time.time() - started, 1),
            "cli": cli, "budget": budget,
            "budget_hard_cap": chain_budget.hard_cap_for(budget),
            "served_models": served_models(cli),
            # 예산이 없으면 세션을 끊는 것은 시간뿐이다. 시간에 걸려 끊긴
            # 세션은 인계 문서를 못 쓰고 끝나므로, 몇 세션이 그렇게 끊겼는지가
            # 그 갈래를 판단하는 값이다.
            "timed_out": bool(cli.get("timed_out")),
            "timeout_s": timeout_s,
            "cut_at": cut_at,
            "call_allowance": allowance,
        }

        transcript = collect_transcript(workdir, cli, out_dir, label, seen)
        row["transcript"] = str(transcript) if transcript else None
        # **끊긴 세션을 세션 기록에 남긴다.** 나중에 "끊긴 자리마다 다음
        # 세션이 무엇을 했는가"를 세려면 어느 세션이 끊겼는지가 필요하다.
        was_cut = cut_hook.cut_marks(workdir.parent) > marks_before
        cut_streak = cut_streak + 1 if was_cut else 0
        row["cut"] = was_cut
        row["cut_streak"] = cut_streak
        row["max_cut_streak"] = max_cut_streak
        if transcript:
            row["audit"] = audit_session(transcript, rules=rules,
                                         relevant_files=relevant)
        # Scored at the seam, kept from the session.
        row["grade"] = grade(task_dir, workdir)
        # **세션이 어떻게 끝났는지를 완료 조건과 따로 적는다.** 2026-08-23에
        # 이것이 없어서 중단된 세션 서른여섯을 "일찍 멈춘 세션" 으로 잘못
        # 읽었다(`docs/EARLY_STOP_SESSIONS.md`).
        row["outcome"] = technical_outcome(row)
        (out_dir / f"session-{label}.json").write_text(
            json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
        rows.append(row)
        used += calls_of(row)
        row["calls_used_in_chain"] = used

        print(f"  {label}  {row['wall_s']:>6.1f}s  "
              f"{progress_line(row['grade'])}")

        # CLI가 아예 시작하지 못했으면 **배치를 멈춘다.** 다음 세션도 같은
        # 이유로 안 돌 것이고, 계속 돌리면 한 번도 실행되지 않은 세션 열 개가
        # 정상 완주로 기록된다. 2026-08-21에 실제로 그렇게 될 뻔했다 —
        # 컨테이너가 root라 CLI가 플래그를 거부했고, 다섯 세션이 각각 0.8초
        # 만에 끝났는데 러너는 넘어갔다.
        if session_never_started(cli):
            print(f"ABORT: {label} 에서 CLI 가 세션을 시작하지 못했다 — "
                  f"종료 코드 {cli.get('exit_code')}. "
                  f"stderr: {str(cli.get('stderr_tail', ''))[:300]}",
                  file=sys.stderr)
            raise SystemExit(3)
    return rows


def served_models(cli: dict) -> list[str]:
    """이 세션을 실제로 서빙한 모델들.

    **사전 예측 문서가 모델을 조건으로 적는데, 지금까지 그것을 확인하는
    기록이 어디에도 없었다.** `--model` 을 안 주면 CLI 기본값이 쓰이고,
    `meta.json` 에는 `null` 이 남는다. 2026-08-21에 서브시스템 보정 배치 4차를
    `--model` 없이 시작했다 — 실제로 서빙한 모델은 앞 배치들과 같았지만
    (`claude-sonnet-5`), 기록만으로는 그것을 확인할 수 없었고 배치 도중에
    기본값이 바뀌어도 드러나지 않았을 것이다.

    보조 모델이 섞여 나오는 것은 정상이다 — 요약이나 제목 생성에 작은 모델이
    쓰인다. 그래서 하나로 접지 않고 나온 것을 전부 적는다.
    """
    usage = cli.get("modelUsage")
    return sorted(usage) if isinstance(usage, dict) else []


def progress_name(rows: list[dict]) -> str:
    """`per_session_scores` 가 무엇을 센 수인가.

    **과제마다 다르다.** 옛 과제들은 마일스톤 통과 수이고, 큐 과제는 항목 통과
    수다. 2026-08-28 전에는 실행 중 출력이 어느 과제에서든 `마일스톤` 이라고
    적었다(`docs/QUEUE_TASK_DEFECTS.md` 10-3).
    """
    for row in rows:
        grade = row.get("grade") or {}
        if isinstance(grade.get("milestone_score"), int):
            return "마일스톤"
        if isinstance(grade.get("met"), int):
            return "항목 통과"
    return "진척"


def chain_summary(rows: list[dict]) -> dict:
    """Chain-level roll-up. The session is not the unit of analysis here."""
    scores = [p for p in (progress_of(r["grade"]) for r in rows)
              if isinstance(p, int)]
    gains = [b - a for a, b in zip(scores, scores[1:])] if len(scores) > 1 else []
    final = rows[-1]["grade"] if rows else {}
    return {
        "sessions": len(rows),
        "counted": progress_name(rows),
        "final_milestone_score": final.get("milestone_score"),
        "final_violations": final.get("violations"),
        # 큐 과제 셋은 채점기 출력의 열쇠가 달라 위 둘이 비어 있다.
        "final_progress": progress_of(final),
        "per_session_scores": scores,
        "per_session_gain": gains,
        "stalled_sessions": sum(1 for g in gains if g <= 0),
        "total_wall_s": round(sum(r["wall_s"] for r in rows), 1),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("task_dir")
    ap.add_argument("--chains", type=int, default=1)
    ap.add_argument("--sessions", type=int, default=6)
    ap.add_argument("--budget", type=int, default=60,
                    help="tool calls per session; 0 이면 예산 훅을 아예 "
                         "배선하지 않고 --timeout-min 으로만 제한한다")
    ap.add_argument("--out", default="results/chain")
    ap.add_argument("--model", default=None)
    ap.add_argument("--timeout-min", type=int, default=40)
    ap.add_argument("--resume", action="store_true",
                    help="continue chains that already have finished sessions")
    ap.add_argument("--cut-at", type=int, default=0,
                    help="이 호출까지 .py 파일을 한 번도 안 연 세션을 그 자리에서 "
                         "끊는다. 0이면 안 끊는다.")
    ap.add_argument("--max-cut-streak", type=int, default=2,
                    help="연속으로 끊을 수 있는 세션 수의 상한. 이 수만큼 "
                         "연달아 끊긴 뒤에는 다음 세션을 신호가 켜져도 안 "
                         "끊는다. 0이면 상한이 없다.")
    ap.add_argument("--call-allowance", type=int, default=0,
                    help="사슬 하나가 쓸 도구 호출 총량. 주면 세션 수가 아니라 "
                         "이 총량이 다 될 때까지 돌린다 — 끊는 조건과 안 끊는 "
                         "조건에서 쓴 호출 수를 같게 맞추기 위해서다.")
    args = ap.parse_args(argv)

    task_dir = Path(args.task_dir).resolve()
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    logged_in, email = check_auth()
    if not logged_in:
        print("ABORT: claude CLI is not authenticated - run `claude auth login`",
              file=sys.stderr)
        return 2

    # **제한 시간을 여기 적는다.** 예산이 0이면 세션을 끝내는 것은 시간뿐인데,
    # 2026-08-27 실측의 `meta.json` 에는 그 값이 없었다. 배치를 묶는 조건이
    # 배치 기록에 없으면 나중에 결과를 읽을 때 무엇 안에서 나온 값인지 알 수
    # 없다(`docs/QUEUE_TASK_DEFECTS.md` 10-2).
    meta = {"task": task_dir.name, "chains": args.chains,
            "sessions_per_chain": args.sessions, "budget": args.budget,
            "timeout_min": args.timeout_min,
            "model": args.model, "account": email,
            "cut_at": args.cut_at, "call_allowance": args.call_allowance,
            "max_cut_streak": args.max_cut_streak}
    (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    summaries = []
    for chain in range(1, args.chains + 1):
        print(f"chain {chain}/{args.chains}")
        rows = run_chain(task_dir, out_dir, chain, args.sessions, args.budget,
                         args.model, args.timeout_min * 60, resume=args.resume,
                         cut_at=args.cut_at, allowance=args.call_allowance,
                         max_cut_streak=args.max_cut_streak)
        summary = chain_summary(rows)
        summaries.append(summary)
        print(f"  → {summary['counted']} {summary['per_session_scores']} "
              f"세션마다의 증가 {summary['per_session_gain']}")

    (out_dir / "chains.json").write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
