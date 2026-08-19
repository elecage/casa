"""Evaluate the pre-registered alarm rules against collected sessions.

Judged against docs/ALARM_RULE.md sections 8 (predictions) and 9 (failure
criteria), both written before any of this ran. Thresholds are read from
`casa.alarm`; this script never changes them. Retuning means editing
docs/ALARM_RULE.md and recording why in the STATUS.md decision log.

Two evaluation targets, kept apart on purpose:

  success   the graded outcome. Never an input to the alarm, so using it
            here is not circular (docs/RESTART_EVALUATION.md section 0).
  cost      total assistant output tokens. Also never an input. This is the
            one that matters — the alarm detects waste, not failure, and a
            session that thrashed for twenty calls wasted them whether or
            not it eventually passed.

Usage:
    python pilot/analysis/alarm_eval.py results/main2/* results/main/*
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

# Windows consoles default to a legacy codepage; the report is UTF-8.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ability_early import token_prefix  # noqa: E402
from casa.alarm import THRESHOLDS, alarm_summary  # noqa: E402
from casa.transcript import parse  # noqa: E402


def load_condition(directory: Path) -> list[dict]:
    """One row per session: alarm state, graded outcome, tokens spent."""
    rows = []
    for transcript in sorted(directory.glob("transcript-*.jsonl")):
        number = transcript.name.split("transcript-")[1].split(".")[0]
        row = alarm_summary(parse(transcript))
        row["condition"] = directory.name
        row["session"] = number

        meta = directory / f"session-{number}.json"
        grade = {}
        if meta.exists():
            try:
                grade = (json.loads(meta.read_text(encoding="utf-8")) or {}).get(
                    "grade") or {}
            except ValueError:
                grade = {}
        row["success"] = grade.get("success")

        tokens = token_prefix(transcript)
        row["total_tokens"] = tokens[-1] if tokens else None
        tau = row["tau_alert"]
        row["tokens_at_alert"] = (
            tokens[tau] if tau is not None and tau < len(tokens) else None)
        row["tokens_after_alert"] = (
            row["total_tokens"] - row["tokens_at_alert"]
            if row["total_tokens"] is not None and row["tokens_at_alert"] is not None
            else None)
        rows.append(row)
    return rows


def _rate(rows: list[dict], key: str) -> float:
    return sum(1 for r in rows if r[key]) / len(rows) if rows else 0.0


def _median(values: list) -> float | None:
    clean = [v for v in values if v is not None]
    return statistics.median(clean) if clean else None


def report(rows: list[dict]) -> dict:
    ok = [r for r in rows if r["success"] is True]
    bad = [r for r in rows if r["success"] is False]
    alerted = [r for r in rows if r["ever_alerted"]]
    quiet = [r for r in rows if not r["ever_alerted"]]

    print(f"\n세션 {len(rows)}  성공 {len(ok)}  실패 {len(bad)}  "
          f"라벨 없음 {len(rows) - len(ok) - len(bad)}")

    print("\n[사전 등록 기준 1] 헛경보 — 성공한 세션에 알림이 20%를 넘는가")
    print(f"    성공 세션 알림율 {_rate(ok, 'ever_alerted'):.1%}  "
          f"종료 권고율 {_rate(ok, 'ever_stop_recommended'):.1%}")
    print(f"    실패 세션 알림율 {_rate(bad, 'ever_alerted'):.1%}  "
          f"종료 권고율 {_rate(bad, 'ever_stop_recommended'):.1%}")

    print("\n[사전 등록 기준 3] 무용 — 종료 권고가 0회이고 알림도 끝물에만 뜨는가")
    positions = [r["first_alert_position"] for r in alerted]
    print(f"    알림 {len(alerted)}건, 종료 권고 "
          f"{sum(1 for r in rows if r['ever_stop_recommended'])}건")
    if positions:
        print(f"    첫 알림 위치(세션 진행률) 중앙값 {_median(positions):.2f}  "
              f"최소 {min(positions):.2f}  최대 {max(positions):.2f}")

    print("\n[해제] 알림이 뜬 뒤 세션이 스스로 빠져나온 비율")
    if alerted:
        print(f"    {_rate(alerted, 'alert_cleared'):.0%} "
              f"({sum(1 for r in alerted if r['alert_cleared'])}/{len(alerted)})")

    print("\n[비용] 알림이 뜬 세션이 실제로 더 비쌌는가 (출력 토큰)")
    print(f"    알림 있음 중앙값 {_median([r['total_tokens'] for r in alerted])}")
    print(f"    알림 없음 중앙값 {_median([r['total_tokens'] for r in quiet])}")
    print(f"    알림 이후 소비 중앙값 "
          f"{_median([r['tokens_after_alert'] for r in alerted])}  "
          f"= 끊었다면 아꼈을 양")

    print("\n[규칙별 발화 세션 수]")
    for rule in THRESHOLDS:
        a = sum(1 for r in rows if rule in r["first_alert_by_rule"])
        s = sum(1 for r in rows if rule in r["first_stop_by_rule"])
        print(f"    {rule:<24} 알림 {a:>3}   종료 {s:>3}")

    return {
        "n": len(rows),
        "alert_rate_success": _rate(ok, "ever_alerted"),
        "alert_rate_failure": _rate(bad, "ever_alerted"),
        "cleared_rate": _rate(alerted, "alert_cleared"),
        "median_position": _median(positions),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("dirs", nargs="+", type=Path)
    ap.add_argument("--per-session", action="store_true",
                    help="list every session that raised an alarm")
    args = ap.parse_args(argv)

    rows: list[dict] = []
    for directory in args.dirs:
        if directory.is_dir():
            rows.extend(load_condition(directory))
    if not rows:
        print("트랜스크립트를 찾지 못했다.")
        return 1

    report(rows)
    if args.per_session:
        print("\n[알림이 뜬 세션]")
        for r in rows:
            if r["ever_alerted"]:
                print(f"    {r['condition']}/{r['session']}  호출 {r['n_calls']:>4}  "
                      f"성공={r['success']}  tau={r['tau_alert']}  "
                      f"위치={r['first_alert_position']:.2f}  "
                      f"해제={r['alert_cleared']}  "
                      f"규칙={sorted(r['first_alert_by_rule'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
