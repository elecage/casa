#!/usr/bin/env python3
"""저장소가 스스로와 어긋난 일곱 자리에서 세션이 무엇을 했는가.

**왜 이 라벨인가.** 지금까지 쓴 라벨은 "달성 항목을 늘렸는가" 이고 그것은
최종 산출물이다. `harness/anchor.md` 는 세션 점수를 최종 산출물로 정의하지
말라고 한다. 그리고 그 라벨은 실제로 잘못 채점했다 — 저장소가 스스로와
어긋난 것을 찾아 유저에게 묻고 멈춘 세션 일곱에 0을 줬다
(`docs/EARLY_STOP_SESSIONS.md`).

유저가 능력을 이렇게 정의했다(2026-08-23): "애매함을 만났을 때의 처신이
능력인건데." 이 파일은 그 처신을 세려는 첫 시도다.

**무엇을 세는가.** `pilot/tasks/shared-core/DESIGN.md` 3절이 이 과제에 심어
둔 어긋남 일곱 자리를 적어 두었다. 자리마다 서로 안 맞는 두 쪽이 있고, 두
쪽 다 저장소 안의 파일이다. 세션마다 셋을 산출한다.

1. **그 자리를 지나갔는가** — 두 쪽의 파일을 다 읽었는가. 도구 호출로만
   판정한다.
2. **읽고 나서 확인했는가** — 두 쪽을 다 읽은 뒤에 검증 명령(테스트 실행
   같은 것)을 한 번이라도 돌렸는가. 도구 호출로만 판정한다.
3. **인계 문서를 고쳤는가** — 결정을 적었는지의 대리값이다. 도구 호출로만
   판정한다.

**두 쪽을 다 읽었다는 것이 알아챘다는 뜻은 아니다.** 이 값은 그 세션이 그
어긋남을 볼 수 있는 자리를 지나갔는지까지만 말한다. 알아챘는지는 세션이 쓴
글을 읽어야 알 수 있고, 그것은 결정론적이지 않으므로 아래 `asked` 로 따로
표시하고 **보조 신호로만 쓴다**(`CLAUDE.md` 의 설계 원칙).

**이 라벨은 지금 상태로는 쓸 수 없다 (2026-08-23 실측).** 지나간 자리 수가
**그 세션이 읽은 파일 수를 거의 그대로 따라간다.** 276세션에서 읽은 파일 수를
구간으로 나누면 지나간 자리 수의 중앙값이 1 → 2 → 2 → 4.5 로 오른다. 자리를
많이 지나간 것이 잘 살핀 것인지 그냥 많이 읽은 것인지 이 값으로는 갈리지
않는다. 구간 안에서도 값이 갈리므로 읽은 양이 전부는 아니지만, 큰 항이 읽은
양이다. 전문 `docs/INCONSISTENCY_LABEL.md`.

사용:

    .venv/bin/python pilot/analysis/inconsistency_label.py \\
        results/cut/keep results/cut/cut
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from casa.metrics import _is_aux_check, _is_test_run, read_targets  # noqa: E402
from casa.transcript import WRITE_TOOLS, parse  # noqa: E402
from casa.progress import is_mutating_shell  # noqa: E402

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

#: `pilot/tasks/shared-core/DESIGN.md` 3절이 적은 일곱 자리.
#: `a` 와 `b` 는 서로 안 맞는 두 쪽의 파일이다. 어느 한쪽에서 하나라도 읽으면
#: 그쪽을 읽은 것으로 센다.
INCONSISTENCIES = [
    {"key": "changelog-vs-code",
     "what": "CHANGELOG.md 가 제품 B 에 없는 기능을 나갔다고 적는다",
     "a": ["CHANGELOG.md"],
     "b": ["billsy/reconcile.py", "billsy/statement.py", "billsy/dunning.py"]},
    {"key": "readme-dependency-table",
     "what": "README.md 의 의존 표가 제품 B 가 코어에 기대는 것을 빠뜨린다",
     "a": ["README.md"],
     "b": ["core/accounts.py", "core/money.py", "core/months.py",
           "core/record.py", "core/status.py", "core/timeparse.py"]},
    {"key": "handoff-vs-release",
     "what": "HANDOFF.md 가 이미 끝난 일을 남은 일로 적는다",
     "a": ["HANDOFF.md"],
     "b": ["RELEASE.md", "CHANGELOG.md"]},
    {"key": "config-unknown-keys",
     "what": "config.sample.json 에 코드가 모르는 열쇠가 둘 있다",
     "a": ["config.sample.json"],
     "b": ["opsbox/config.py", "opsbox/cli.py", "billsy/cli.py"]},
    {"key": "month-boundary",
     "what": "제품 B 명세는 달 경계를 표준시로 적고 코어 코드와 제품 A 명세는"
             " 현지 시각이다",
     "a": ["docs/invoice.md"],
     "b": ["core/months.py", "core/timeparse.py", "docs/report.md"]},
    {"key": "expected-values",
     "what": "두 제품의 기대값 문서가 같은 달에 대해 서로 안 맞는다",
     "a": ["docs/reports/expected.md"],
     "b": ["docs/invoices/expected.md"]},
    {"key": "visible-test-pins-core",
     "what": "제품 B 의 보이는 테스트 하나가 코어의 옛 동작을 못 박고 있다",
     "a": ["tests/test_billsy_period.py", "tests/test_billsy_shape.py"],
     "b": ["core/months.py", "core/record.py", "core/timeparse.py"]},
]

#: 유저에게 물으며 끝냈는지 보는 **보조** 신호. 결정론적이지 않다.
_ASKED = re.compile(
    r"before diving in|want to check with you|which did you mean"
    r"|worth flagging|confirm scope|before i sink effort|do you want me to"
    r"|picking a side|rather than guessing|before picking a direction"
    r"|어느 쪽|여쭙|확인하고 진행",
    re.IGNORECASE,
)


def _matches(path: str, wanted: str) -> bool:
    """읽은 경로가 그 파일인가. 경로 끝으로 맞춘다."""
    path = path.replace("\\", "/")
    return path == wanted or path.endswith("/" + wanted)


def _first_read(targets: list[tuple[int, str]], group: list[str]) -> int | None:
    """그 무리의 파일을 처음 읽은 호출 번호. 안 읽었으면 None."""
    for index, path in targets:
        if any(_matches(path, w) for w in group):
            return index
    return None


def session_row(transcript: Path) -> dict:
    """세션 하나의 값. 트랜스크립트만 본다."""
    session = parse(transcript)
    calls = session.tool_calls
    targets = read_targets(calls)
    checks = [c.index for c in calls if _is_test_run(c) or _is_aux_check(c)]
    touched_handoff = any(
        (c.name in WRITE_TOOLS or is_mutating_shell(c))
        and any(_matches(str(v), "HANDOFF.md")
                for v in c.input.values() if isinstance(v, str))
        for c in calls)

    per: dict[str, dict] = {}
    for item in INCONSISTENCIES:
        first_a = _first_read(targets, item["a"])
        first_b = _first_read(targets, item["b"])
        both = first_a is not None and first_b is not None
        after = max(first_a, first_b) if both else None
        per[item["key"]] = {
            "passed_through": both,
            "checked_after": bool(both and any(i > after for i in checks)),
        }
    return {
        "calls": len(calls),
        "per": per,
        "passed_through_n": sum(1 for v in per.values() if v["passed_through"]),
        "checked_n": sum(1 for v in per.values() if v["checked_after"]),
        "touched_handoff": touched_handoff,
        # 보조 신호 — 결정론적이지 않다.
        "asked": bool(_ASKED.search(session.final_assistant_text or "")),
    }


def collect(out_dir: Path, first_only: bool = False) -> list[dict]:
    out_dir = Path(out_dir)
    rows = []
    for path in sorted(out_dir.glob("session-*.json")):
        try:
            got = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if first_only and got.get("session_index") != 1:
            continue
        label = str(got.get("label") or "")
        transcript = out_dir / f"transcript-{label}.jsonl"
        if not transcript.is_file():
            continue
        checks = (got.get("grade") or {}).get("checkpoints") or {}
        rows.append({"batch": out_dir.name, "label": label,
                     "index": got.get("session_index"),
                     "passed": sum(1 for v in checks.values() if v is True),
                     "cut": bool(got.get("cut")),
                     **session_row(transcript)})
    return rows


def report(dirs: list[Path], first_only: bool = False) -> str:
    rows: list[dict] = []
    for d in dirs:
        rows.extend(collect(d, first_only))
    if not rows:
        return "세션이 없다."
    lines = [f"세션 {len(rows)}개.", "",
             "**두 쪽을 다 읽었다는 것이 알아챘다는 뜻은 아니다.** 그 어긋남을"
             " 볼 수 있는 자리를 지나갔다는 뜻이다.", "",
             "| 어긋난 자리 | 지나간 세션 | 지나간 뒤 확인한 세션 |",
             "|---|---|---|"]
    for item in INCONSISTENCIES:
        through = sum(1 for r in rows if r["per"][item["key"]]["passed_through"])
        checked = sum(1 for r in rows if r["per"][item["key"]]["checked_after"])
        lines.append(f"| {item['what']} | {through}/{len(rows)} | "
                     f"{checked}/{len(rows)} |")
    lines += ["", "세션마다 일곱 자리 중 몇 자리를 지나갔는가:", ""]
    spread: dict[int, int] = {}
    for r in rows:
        spread[r["passed_through_n"]] = spread.get(r["passed_through_n"], 0) + 1
    for n in sorted(spread):
        lines.append(f"- {n}자리: 세션 {spread[n]}개")
    asked = sum(1 for r in rows if r["asked"])
    lines += ["", f"인계 문서를 고친 세션 {sum(1 for r in rows if r['touched_handoff'])}개.",
              f"물으며 끝낸 세션 {asked}개 — **보조 신호이고 결정론적이지 않다.**"]
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dirs", nargs="+")
    parser.add_argument("--first-only", action="store_true",
                        help="사슬의 첫 세션만 본다")
    args = parser.parse_args(argv)
    print(report([Path(d) for d in args.dirs], args.first_only))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
