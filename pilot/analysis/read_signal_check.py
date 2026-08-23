#!/usr/bin/env python3
"""읽은 대상과 순서를 보는 지표들이 두 집단을 구분하는가.

**사후 탐색이다. 예측을 봉인하지 않았다.** 새 수집 없이 이미 있는 자료로
한다. 앞 세션의 탐색(`docs/EARLY_SIGNAL_SEARCH.md`)은 스크립트를 안 남겨
재현이 안 됐다. 이 파일이 그 자리를 메운다.

**무엇에 적용하는가.** 사슬의 **첫 세션**만 모은다. 첫 세션은 시작 상태가 같으므로
사슬 안의 위치가 섞이지 않는다. 과제 셋에서 48개가 모인다.

**라벨.** 그 세션이 달성 항목을 늘렸는가. 세 과제 다 시작 상태에서 통과해
있는 항목이 1개다(2026-08-23에 각 과제의 채점기를 시작 상태에 실행해 확인:
`release-traps` 14개 중 1개, `shared-core` 58개 중 1개,
`subsystems-deep` 25개 중 1개).

**라벨이 결과라는 것을 적어 둔다.** `harness/anchor.md` 는 세션 점수를 최종
산출물로 정의하지 말라고 한다. 여기서 쓰는 라벨은 그 금지에 걸리는 결과
라벨이고, 지금은 그것 말고 손에 있는 라벨이 없다. 이 지표들이 라벨을 맞히는지
보는 것은 지표를 고르는 첫 걸음이지 세션 점수를 정하는 것이 아니다.

사용:

    .venv/bin/python pilot/analysis/read_signal_check.py \\
        results/main3/subsystems-deep results/chain3/release-traps \\
        results/cut/keep results/cut/cut
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from casa import signals as sig  # noqa: E402
from casa.transcript import Session, parse  # noqa: E402

#: 세 과제 다 시작 상태에서 통과해 있는 항목이 이만큼이다.
START_MARK = 1

#: 읽은 대상과 순서를 보는 지표들. 이 파일이 검정하는 대상.
READ_SIGNALS = ("distinct_read_paths", "doc_read_ratio", "doc_before_first_edit",
                "docs_after_first_edit", "max_reread_gap", "read_before_edit_ratio")

#: 초반 몇 호출까지 보고 판정할 것인가.
WINDOWS = (10, 15, 20)

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


def head(session: Session, window: int) -> Session:
    """앞 `window` 호출만 남긴 세션. 마지막 메시지는 지운다.

    마지막 메시지를 남겨 두면 거기서 계산되는 지표에 정답이 새어 든다.
    이 파일이 보는 지표들은 그것을 안 쓰지만, `compute_signals` 가 산출하는
    지표 전부를 함께 볼 때를 위해 여기서 지운다.
    """
    cut = Session(path=session.path)
    cut.tool_calls = session.tool_calls[:window]
    cut.final_assistant_text = None
    return cut


def batch_budget(out_dir: Path) -> int | None:
    """그 배치가 세션에 준 호출 예산. `meta.json` 이 없거나 못 읽으면 None."""
    try:
        meta = json.loads((Path(out_dir) / "meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    budget = meta.get("budget")
    return budget if isinstance(budget, int) and budget > 0 else None


def first_sessions(out_dir: Path) -> list[dict]:
    """그 배치의 사슬 첫 세션들. 트랜스크립트가 없으면 건너뛴다."""
    out_dir = Path(out_dir)
    budget = batch_budget(out_dir)
    rows: list[dict] = []
    for path in sorted(out_dir.glob("session-*.json")):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if row.get("session_index") != 1:
            continue
        label = str(row.get("label") or "")
        transcript = out_dir / f"transcript-{label}.jsonl"
        if not transcript.is_file():
            continue
        checks = (row.get("grade") or {}).get("checkpoints") or {}
        passed = sum(1 for v in checks.values() if v is True)
        rows.append({
            "task": row.get("task") or out_dir.name,
            "label": label,
            "batch": out_dir.name,
            "passed": passed,
            "advanced": passed > START_MARK,
            "budget": budget,
            "transcript": transcript,
        })
    return rows


def measure(rows: list[dict], window: int) -> list[dict]:
    """세션마다 초반 구간의 지표 값을 붙인다."""
    out: list[dict] = []
    for row in rows:
        session = head(parse(row["transcript"]), window)
        battery = sig.compute_signals(session)
        out.append({**row, "calls_in_window": len(session.tool_calls),
                    **{k: battery[k] for k in READ_SIGNALS}})
    return out


def _numeric(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    return None


def split(measured: list[dict], key: str) -> dict:
    """두 라벨 집단의 값 분포. 값이 없는 세션은 양쪽 다에서 뺀다."""
    up = sorted(v for v in (_numeric(r[key]) for r in measured if r["advanced"])
                if v is not None)
    flat = sorted(v for v in (_numeric(r[key]) for r in measured if not r["advanced"])
                  if v is not None)
    return {"advanced": up, "flat": flat,
            "separated": bool(up and flat
                              and (min(up) > max(flat) or min(flat) > max(up)))}


def _fmt(values: list[float]) -> str:
    if not values:
        return "(없음)"
    body = ", ".join(f"{v:g}" if v == int(v) else f"{v:.2f}" for v in values)
    return body if len(body) <= 60 else body[:57] + "..."


def report(dirs: list[Path], windows=WINDOWS) -> str:
    rows: list[dict] = []
    for d in dirs:
        rows.extend(first_sessions(d))
    lines = [f"첫 세션 {len(rows)}개, 배치 {len(dirs)}곳.", ""]
    by_task: dict[str, list[dict]] = {}
    for row in rows:
        by_task.setdefault(str(row["task"]), []).append(row)
    for task, group in sorted(by_task.items()):
        up = sum(1 for r in group if r["advanced"])
        lines.append(f"- {task}: {len(group)}개, 항목을 늘린 세션 {up}개, "
                     f"늘리지 못한 세션 {len(group) - up}개")
    lines.append("")

    for window in windows:
        measured = measure(rows, window)
        lines.append(f"## 초반 {window}호출")
        lines.append("")
        for task, group in sorted(by_task.items()):
            subset = [m for m in measured if m["task"] == task]
            if len({r["advanced"] for r in subset}) < 2:
                lines.append(f"### {task} — 라벨이 한쪽뿐이라 구분할 것이 없다")
                lines.append("")
                continue
            lines.append(f"### {task}")
            lines.append("")
            lines.append("| 지표 | 항목을 늘린 세션 | 늘리지 못한 세션 | 구분되나 |")
            lines.append("|---|---|---|---|")
            for key in READ_SIGNALS:
                got = split(subset, key)
                mark = "**예**" if got["separated"] else "아니오"
                lines.append(f"| `{key}` | {_fmt(got['advanced'])} | "
                             f"{_fmt(got['flat'])} | {mark} |")
            lines.append("")
    return "\n".join(lines)


def detail(dirs: list[Path]) -> str:
    """세션마다 언제 처음 고쳤고 언제 문서로 돌아갔는지.

    `docs_after_first_edit` 이 0인 것에는 두 가지가 섞여 있다 — 고치기
    시작했는데 문서로 안 돌아간 세션과, **아예 아무것도 안 고친 세션**이다.
    뒤쪽은 그 지표가 산출될 수 없는 자리이지 행동의 차이가 아니다. 이 표는
    둘을 구분해 보기 위한 것이다.
    """
    rows: list[dict] = []
    for d in dirs:
        rows.extend(first_sessions(d))
    lines = ["| 과제 | 라벨 | 호출 수 | 처음 고친 호출 번호 | 고친 뒤 문서 읽기 |"
             " 항목을 늘렸나 |",
             "|---|---|---|---|---|---|"]
    for row in sorted(rows, key=lambda r: (str(r["task"]), r["label"])):
        session = parse(row["transcript"])
        calls = session.tool_calls
        first = sig.first_edit_index(calls)
        back = sig.docs_after_first_edit(calls)
        lines.append(f"| {row['task']} | {row['label']} | {len(calls)} | "
                     f"{'없음' if first is None else first} | {back} | "
                     f"{'예' if row['advanced'] else '아니오'} |")
    return "\n".join(lines)


#: 예산의 몇 할 지점에서 판정할 것인가.
FRACTIONS = (0.3, 0.4, 0.5, 0.6, 0.67, 0.75, 0.83, 0.9)


def guess_before(row: dict, limit: int) -> bool:
    """`limit` 번째 호출까지만 보고 "이 세션은 항목을 늘린다" 라고 예측할 것인가.

    판정 규칙은 하나다 — **그 지점까지 파일을 한 번이라도 고쳤는가.**
    이 값은 그 지점까지의 호출만으로 정해진다. 뒤를 보지 않는다.
    """
    session = parse(row["transcript"])
    return sig.first_edit_index(session.tool_calls[:limit]) is not None


def guess_at(row: dict, fraction: float) -> bool | None:
    """예산의 `fraction` 지점에서 판정한다. 예산을 모르면 None."""
    budget = row.get("budget")
    if not budget:
        return None
    return guess_before(row, int(budget * fraction))


def guess_with_left(row: dict, calls_left: int) -> bool | None:
    """예산이 `calls_left` 개 남은 지점에서 판정한다. 예산을 모르면 None.

    **`guess_at` 과 같은 규칙을 다르게 매개변수화한 것이다.** 판정 자리를
    예산에 견준 비율로 정하느냐, 예산에서 뺀 절대 호출 수로 정하느냐만 다르다.

    이 구별이 중요한 이유는 이렇다. 절대 호출 수로 판정되면, 그 규칙이 잡는
    것은 **일을 끝낼 호출이 남아 있는가**이지 세션의 능력이 아니다.
    """
    budget = row.get("budget")
    if not budget:
        return None
    return guess_before(row, max(budget - calls_left, 0))


def majority_rate(rows: list[dict]) -> float:
    """세션을 하나도 관측하지 않고 많은 쪽 라벨로 전부 예측했을 때의 정답률.

    관측이 필요 없는 이 값을 넘지 못하면 그 지표는 쓸모가 없다.
    """
    if not rows:
        return 0.0
    up = sum(1 for r in rows if r["advanced"])
    return max(up, len(rows) - up) / len(rows)


#: 예산이 몇 호출 남은 지점에서 판정할 것인가.
CALLS_LEFT = (2, 4, 5, 6, 8, 10, 15, 20, 30, 40)


def _scan(rows: list[dict], settings: list, guess, label) -> str:
    """판정 자리를 바꿔 가며 맞힌 세션 수를 센다.

    `guess(row, setting)` 은 그 자리까지만 보고 낸 예측이거나, 판정할 수
    없으면 None 이다. `label(setting)` 은 표의 첫 칸에 들어갈 글이다.
    """
    tasks = sorted({str(r["task"]) for r in rows})
    head = [f"- {task}: {len([r for r in rows if str(r['task']) == task])}개, "
            f"많은 쪽 라벨로 전부 예측하면 "
            f"{majority_rate([r for r in rows if str(r['task']) == task]):.0%}"
            for task in tasks]
    head += ["", f"전체 {len(rows)}개, 많은 쪽 라벨로 전부 예측하면 "
                 f"{majority_rate(rows):.0%}", "",
             "표의 값은 맞힌 세션 수 / 판정한 세션 수다.", "",
             "| 판정 자리 | " + " | ".join(tasks) + " | 전체 |",
             "|---" * (len(tasks) + 2) + "|"]
    for setting in settings:
        cells = []
        hit_all = judged_all = 0
        for task in tasks:
            hit = judged = 0
            for row in (r for r in rows if str(r["task"]) == task):
                got = guess(row, setting)
                if got is None:
                    continue
                judged += 1
                hit += int(got == row["advanced"])
            hit_all += hit
            judged_all += judged
            cells.append(f"{hit}/{judged}" if judged else "판정 못 함")
        total = f"{hit_all}/{judged_all}" if judged_all else "판정 못 함"
        head.append(f"| {label(setting)} | " + " | ".join(cells) + f" | {total} |")
    return "\n".join(head)


def position_scan(rows: list[dict], fractions=FRACTIONS) -> str:
    """예산의 몇 할 지점에서 판정하면 몇 개를 맞히는가.

    앞 세션의 후보들이 남겨 둔 자료에서 두 집단을 구분하지 못한 이유가
    **절대 호출 수 문턱은 과제를 넘지 못한다** 였다
    (`docs/EARLY_SIGNAL_SEARCH.md`). 같은 20호출이 예산 30인 과제에서는
    중반이고 예산 100인 과제에서는 초반이다. 그래서 여기서는 호출 수가 아니라
    그 과제의 예산에 견준 자리로 판정한다.
    """
    return _scan(rows, list(fractions), guess_at, lambda f: f"예산의 {f:.0%}")


def left_scan(rows: list[dict], calls_left=CALLS_LEFT) -> str:
    """예산이 몇 호출 남은 지점에서 판정하면 몇 개를 맞히는가.

    `position_scan` 과 **같은 규칙을 다르게 매개변수화한 것이다.** 둘을 나란히
    놓는 이유는 어느 쪽 매개변수가 과제를 넘는지 보기 위해서다.

    비율 쪽이 잘 맞으면 그 규칙이 잡는 것은 세션이 예산을 어떻게 배분했는가에
    가깝다. **남은 호출 수 쪽이 잘 맞으면 그 규칙이 잡는 것은 일을 끝낼 호출이
    남아 있는가이고, 그것은 세션의 능력이 아니다.**
    """
    return _scan(rows, list(calls_left), guess_with_left,
                 lambda k: f"{k}호출 남은 자리")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dirs", nargs="+", help="배치 출력 디렉터리들")
    parser.add_argument("--windows", default=",".join(str(w) for w in WINDOWS),
                        help="초반 몇 호출까지 볼 것인가. 쉼표로 나열한다. "
                             "세션 전체를 보려면 큰 수를 넣는다.")
    parser.add_argument("--detail", action="store_true",
                        help="세션마다 처음 고친 자리와 고친 뒤 문서 읽기 횟수")
    parser.add_argument("--position", action="store_true",
                        help="예산의 몇 할 지점에서 판정하면 몇 개를 맞히는가")
    parser.add_argument("--left", action="store_true",
                        help="예산이 몇 호출 남은 자리에서 판정하면 몇 개를 맞히는가")
    args = parser.parse_args(argv)
    dirs = [Path(d) for d in args.dirs]
    if args.detail:
        print(detail(dirs))
        return 0
    if args.position or args.left:
        rows: list[dict] = []
        for d in dirs:
            rows.extend(first_sessions(d))
        print(left_scan(rows) if args.left else position_scan(rows))
        return 0
    windows = tuple(int(w) for w in args.windows.split(",") if w.strip())
    print(report(dirs, windows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
