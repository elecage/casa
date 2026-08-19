"""Is killing an alarmed session actually worth it? (docs/RESTART_EVALUATION.md)

Answers the two questions that decide whether the whole detector is useful:

  (a) if you do NOT kill, does it actually go badly?
      Every collected session ran to the end, so this is observed, not
      modelled. The number that matters is the recovery rate — how often an
      alarmed session got out of it by itself.

  (b) would killing and restarting have been cheaper?
      The restart arm is drawn from other sessions in the same batch. Session
      independence was checked separately (pilot/analysis/session_independence),
      which is what licenses treating them as exchangeable.

Two null policies are computed alongside, because in a low-success condition
"kill everything early and re-roll" improves tokens-per-success on arithmetic
alone. A signal that cannot beat that has contributed nothing.

Evaluation uses only quantities the alarm never sees: graded outcome and
output tokens (docs/RESTART_EVALUATION.md section 0).

Usage:
    python pilot/analysis/restart_eval.py results/main2/* results/main/*
"""

from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from ability_early import token_prefix  # noqa: E402
from alarm_eval import load_condition  # noqa: E402
from casa.transcript import parse  # noqa: E402


def enrich(directory: Path) -> list[dict]:
    """Add the restart-economics fields alarm_eval does not carry."""
    rows = load_condition(directory)
    for row in rows:
        transcript = directory / f"transcript-{row['session']}.jsonl"
        tokens = token_prefix(transcript)
        session = parse(transcript)
        first_edit = next(
            (c.index for c in session.tool_calls if c.is_mutation), None)
        # Cost of getting oriented before changing anything. A restart has to
        # pay this again, so it sets the floor on what killing can save.
        row["context_cost"] = (
            tokens[first_edit] if first_edit is not None and first_edit < len(tokens)
            else None)
    return rows


def _median(values) -> float | None:
    clean = [v for v in values if v is not None]
    return statistics.median(clean) if clean else None


def recovery(rows: list[dict]) -> None:
    alerted = [r for r in rows if r["ever_alerted"]]
    print("\n[질문 a] 안 끊고 계속하면 정말 문제가 되는가")
    if not alerted:
        print("    알림이 뜬 세션이 없다.")
        return
    cleared = [r for r in alerted if r["alert_cleared"]]
    succeeded = [r for r in alerted if r["success"] is True]
    print(f"    알림 세션 {len(alerted)}건")
    print(f"    스스로 알림이 풀린 비율   {len(cleared) / len(alerted):.0%} "
          f"({len(cleared)}/{len(alerted)})")
    print(f"    결국 성공한 비율          {len(succeeded) / len(alerted):.0%} "
          f"({len(succeeded)}/{len(alerted)})")
    print("    → 이 비율이 높으면 알림 시점의 종료는 성공을 죽이는 것이다.")


def policies(rows: list[dict]) -> None:
    """Tokens per success under three policies, nulls included."""
    print("\n[질문 b] 끊는 정책이 안 끊는 정책보다 나은가 (성공 하나당 토큰)")
    graded = [r for r in rows
              if r["success"] is not None and r["total_tokens"] is not None]
    if not graded:
        print("    채점된 세션이 없다.")
        return

    total_tokens = sum(r["total_tokens"] for r in graded)
    successes = sum(1 for r in graded if r["success"])
    base_rate = successes / len(graded)
    fresh_cost = _median([r["total_tokens"] for r in graded]) or 0.0

    def per_success(tokens: float, wins: float) -> str:
        return f"{tokens / wins:,.0f}" if wins else "성공 0"

    print(f"    전부 계속        {per_success(total_tokens, successes)}"
          f"   (성공 {successes}/{len(graded)})")

    # Kill everything at the median alarm point, then re-roll once.
    cut = _median([r["tau_alert"] for r in rows if r["tau_alert"] is not None])
    if cut is not None:
        killed_tokens = 0.0
        for r in graded:
            tokens = token_at(r, int(cut))
            killed_tokens += (tokens if tokens is not None else r["total_tokens"])
        killed_tokens += len(graded) * fresh_cost
        print(f"    전부 끊고 재시작 {per_success(killed_tokens, len(graded) * base_rate)}"
              f"   ← 귀무 정책. 신호를 전혀 쓰지 않는다")

    alarm_tokens = 0.0
    alarm_wins = 0.0
    killed_successes = 0
    for r in graded:
        if r["ever_stop_recommended"]:
            spent = token_at(r, r["tau_stop"]) or r["total_tokens"]
            alarm_tokens += spent + fresh_cost
            alarm_wins += base_rate
            if r["success"]:
                killed_successes += 1
        else:
            alarm_tokens += r["total_tokens"]
            alarm_wins += 1 if r["success"] else 0
    print(f"    경보 기반 종료   {per_success(alarm_tokens, alarm_wins)}"
          f"   (죽인 세션 중 성공이었을 것 {killed_successes}건 = 오탐 비용)")


def token_at(row: dict, index: int | None) -> float | None:
    """Spend at a call index, when the row carries enough to say."""
    if index is None:
        return None
    if row.get("tau_alert") == index and row.get("tokens_at_alert") is not None:
        return row["tokens_at_alert"]
    if row["total_tokens"] is None or not row["n_calls"]:
        return None
    return row["total_tokens"] * min(index / row["n_calls"], 1.0)


def break_even(rows: list[dict]) -> None:
    """How much work must remain for killing to pay.

    Killing is only worth it when the waste avoided exceeds the cost of
    getting a new session oriented again:

        continue  = remaining work x m        (m = waste multiplier)
        restart   = H + remaining work        (H = context re-establishment)
        pays iff    remaining > H / (m - 1)
    """
    alerted = [r for r in rows if r["ever_alerted"] and r["total_tokens"]]
    quiet = [r for r in rows if not r["ever_alerted"] and r["total_tokens"]]
    context = _median([r["context_cost"] for r in rows])
    if not alerted or not quiet or not context:
        print("\n[손익분기] 계산에 필요한 표본이 부족하다.")
        return

    alerted_cost = _median([r["total_tokens"] for r in alerted])
    quiet_cost = _median([r["total_tokens"] for r in quiet])
    m = alerted_cost / quiet_cost
    remaining = _median([r["tokens_after_alert"] for r in alerted]) or 0.0
    session_cost = _median([r["total_tokens"] for r in rows]) or 0.0
    position = _median([r["first_alert_position"] for r in alerted]) or 0.0

    print("\n[손익분기] 끊어서 이득이 되려면 남은 일이 얼마나 되어야 하는가")
    print(f"    H  문맥 재확보 비용(첫 편집 전 소비) 중앙값   {context:>10,.0f} 토큰")
    print(f"    m  낭비 배수(알림 세션 / 무알림 세션 비용)    {m:>10.2f}")
    print(f"    손익분기: 남은 일 > H/(m-1)                   {context / (m - 1):>10,.0f} 토큰")
    print(f"    실제 알림 이후 남은 양                        {remaining:>10,.0f} 토큰")
    print(f"    → 실제가 손익분기의 {remaining / (context / (m - 1)):.2f}배")
    if position < 1:
        need = (context / (m - 1)) / (1 - position)
        print(f"\n    알림이 세션의 {position:.0%} 지점에 뜨므로, 이득이 되려면")
        print(f"    세션 총량이 {need:>10,.0f} 토큰은 되어야 한다 "
              f"(현재 중앙값 {session_cost:,.0f}, 약 {need / session_cost:.0f}배)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("dirs", nargs="+", type=Path)
    args = ap.parse_args(argv)

    rows: list[dict] = []
    for directory in args.dirs:
        if directory.is_dir():
            rows.extend(enrich(directory))
    if not rows:
        print("트랜스크립트를 찾지 못했다.")
        return 1

    print(f"세션 {len(rows)}")
    recovery(rows)
    policies(rows)
    break_even(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
