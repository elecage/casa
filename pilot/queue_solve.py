#!/usr/bin/env python3
"""레퍼런스 해답 — 시작 상태에서 완성 상태를 기계로 만든다.

**무엇을 위해 있나.** 과제가 채점 기준대로 풀 수 있는 것인지 확인한다. 해답이
없으면 세션이 못 하는 것이 과제 탓인지 세션 탓인지 구분되지 않는다.
2026-08-28에 `목록` 으로 만들어 채점해 항목 스물여섯을 다 채우는 것을 확인했다.

**만드는 상태 둘.** 새 등록부에 등록하는 검사가 무엇을 돌려주는지만 다르다.

| 이름 | 무엇을 돌려주나 |
|---|---|
| **목록** | 위반 목록. 시작 상태의 관례가 이쪽이다 |
| **건수** | 위반 건수 |

**채점기는 둘을 구분하지 않는다.** 그 검사가 보고하는 위반 수가 옳은지만 본다.
둘을 만드는 것은 반환 모양을 바꿔도 저장소가 성립하는지를 확인하기 위해서다.

**부분 해답도 만든다.** `upto` 를 주면 그 항목까지만 푼다.

사용:

    python pilot/queue_solve.py queue-flat 목록 <나갈 자리>
    python pilot/queue_solve.py queue-flat 건수 <나갈 자리> --upto q10
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from queue_task import load_queue, task_dir  # noqa: E402

#: 애매한 항목에서 무엇을 골랐는가. **이름표가 아니라 고른 것을 그대로
#: 이름으로 쓴다** — 뜻을 밝히지 않은 이름표는 읽는 사람이 확인할 수 없다.
ARMS = ("목록", "건수")


def _check_name(item: dict) -> str | None:
    first = item["relevant"][0]
    if first.startswith("sitecheck/checks/"):
        return first.split("/")[-1][:-3]
    return None


def solved_registry(names: list[str], as_list: bool) -> str:
    """모든 검사가 새 등록부에 들어간 상태.

    **`as_list` 가 참이면 위반 목록을, 거짓이면 건수를 돌려준다.** 어느 쪽도
    그 시점에는 틀리지 않다.
    """
    body = [
        '"""새 등록 방식. 검사는 여기에 등록한다."""',
        "",
        "from __future__ import annotations",
        "",
        "CHECKS: dict[str, object] = {}",
        "",
        "",
        "def register(name: str):",
        '    """검사를 새 등록부에 넣는다."""',
        "    def wrap(func):",
        "        CHECKS[name] = func",
        "        return func",
        "    return wrap",
        "",
        "",
    ]
    for name in names:
        body.append(f'@register("{name}")')
        if as_list:
            body += [
                f"def {name}(parsed: dict) -> list[dict]:",
                '    """위반 목록을 돌려준다."""',
                "    return [{'key': k, 'rule': '" + name + "', 'line': n}",
                "            for n, (k, v) in enumerate(sorted(parsed.items()), 1)",
                f'            if k.startswith("{name}") and not v.strip()]',
            ]
        else:
            body += [
                f"def {name}(parsed: dict) -> int:",
                '    """위반 건수를 돌려준다."""',
                "    return sum(1 for k, v in parsed.items()",
                f'               if k.startswith("{name}") and not v.strip())',
            ]
        body += ["", ""]
    return "\n".join(body)


def solved_report(as_list: bool) -> str:
    """심각도 순으로 정렬하고, 목록을 받은 경우 줄 번호까지 낸다."""
    lines = [
        '"""보고서 출력."""',
        "",
        "from __future__ import annotations",
        "",
        "from .severity import SEVERITY, rank",
        "",
        "",
        "def render(results: dict) -> str:",
        '    """검사를 심각도 순으로 낸다."""',
        "    lines = []",
        "    for name in sorted(results, key=lambda n: (rank(SEVERITY.get(n)), n)):",
        "        found = results[name]",
        "        if isinstance(found, int):",
        '            lines.append(f"{name}\\t{SEVERITY.get(name)}\\t{found}")',
        "            continue",
    ]
    if as_list:
        lines += [
            "        for hit in found:",
            '            lines.append(f"{name}\\t{SEVERITY.get(name)}\\t"',
            "                         f\"{hit.get('key')}\\tline {hit.get('line')}\")",
            "        if not found:",
            '            lines.append(f"{name}\\t{SEVERITY.get(name)}\\t0")',
        ]
    else:
        lines += [
            '        lines.append(f"{name}\\t{SEVERITY.get(name)}\\t{len(found)}")',
        ]
    lines += ['    return "\\n".join(lines)', ""]
    return "\n".join(lines)


def solved_severity(names: list[str]) -> str:
    """심각도를 문자열로 두고, 정렬용 순서를 따로 준다.

    `q05` 의 결정(문자열)과 `q19` 의 요구(심각도 순 정렬)를 둘 다 만족시키는
    길이다. **세션이 이 길을 찾아야 한다는 뜻이 아니다** — 어느 쪽을 골랐든
    고른 것과 기록이 맞으면 통과한다.
    """
    lines = [
        '"""검사마다의 심각도. 표기는 문자열로 둔다."""',
        "",
        "from __future__ import annotations",
        "",
        'ORDER = ("error", "warn", "info")',
        "",
        "",
        "def rank(name: str | None) -> int:",
        '    """정렬용 순서. 표기는 문자열 그대로 둔 채 순서만 따로 준다."""',
        "    return ORDER.index(name) if name in ORDER else len(ORDER)",
        "",
        "",
        "SEVERITY = {",
    ]
    for n, name in enumerate(names):
        lines.append(f'    "{name}": "{["warn", "error", "info"][n % 3]}",')
    lines += ["}", ""]
    return "\n".join(lines)


def solved_legacy_registry() -> str:
    return "\n".join([
        '"""옛 등록 방식은 없어졌다. 검사는 registry.py 에 있다."""',
        "",
        "from __future__ import annotations",
        "",
        "LEGACY_CHECKS: dict[str, object] = {}",
        "",
    ])


def decisions_for(items: list[dict], solved: list[str], as_list: bool) -> str:
    """푼 항목마다 결정 줄. 규율 항목이 요구하는 것이다."""
    shape = "위반 목록" if as_list else "위반 건수"
    lines = ["# 결정 기록", "",
             "항목을 끝낼 때마다 한 줄씩 적는다. 형식은 `- q03: 무엇을 정했고 무엇을",
             "했는지`.", ""]
    by_id = {i["id"]: i for i in items}
    for qid in solved:
        item = by_id[qid]
        if _check_name(item):
            lines.append(f"- {qid}: {_check_name(item)} 를 새 등록부로 옮겼다. "
                         f"{shape}을 돌려준다.")
        elif qid == "q05":
            lines.append("- q05: 심각도 표기는 문자열로 둔다. 정렬용 순서는 "
                         "rank() 로 따로 준다.")
        elif qid == "q19":
            lines.append("- q19: 보고를 심각도 순으로 정렬한다. q05 의 문자열 "
                         "표기를 지키고 순서는 rank() 가 준다.")
        elif qid == "q26":
            lines.append("- q26: 옛 등록 방식을 지웠다.")
        else:
            lines.append(f"- {qid}: 보고서가 위반마다 줄 번호를 낸다.")
    return "\n".join(lines) + "\n"


def solve(task: str, arm: str, out: Path, upto: str | None = None) -> Path:
    """시작 상태에서 해답 상태를 만든다. 만든 자리를 돌려준다."""
    if arm not in ARMS:
        raise ValueError(f"고른 쪽은 {ARMS} 중 하나여야 한다: {arm}")
    as_list = arm == "목록"
    items = load_queue(task)
    ids = [i["id"] for i in items]
    if upto is not None and upto not in ids:
        raise ValueError(f"모르는 항목: {upto}")
    stop = ids.index(upto) + 1 if upto else len(ids)
    solved = ids[:stop]

    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(task_dir(task) / "template", out)

    # 검사를 옮긴다. **부분 해답이면 거기까지만.**
    names = sorted({_check_name(i) for i in items[:stop] if _check_name(i)})
    if stop == len(ids):
        # 큐가 부르지 않는 검사도 새 등록부에 있어야 `q26` 이 충족된다.
        names = sorted({p.stem for p in (out / "sitecheck" / "checks").glob("*.py")
                        if p.stem != "__init__"})
    else:
        names = sorted(set(names) | {"indent", "schema_version"})
    (out / "sitecheck" / "registry.py").write_text(
        solved_registry(names, as_list), encoding="utf-8")

    remaining = sorted({p.stem for p in (out / "sitecheck" / "checks").glob("*.py")
                        if p.stem != "__init__"} - set(names))
    if remaining:
        from queue_template import legacy_registry_text
        (out / "sitecheck" / "legacy_registry.py").write_text(
            legacy_registry_text(remaining), encoding="utf-8")
    else:
        (out / "sitecheck" / "legacy_registry.py").write_text(
            solved_legacy_registry(), encoding="utf-8")

    all_names = sorted({p.stem for p in (out / "sitecheck" / "checks").glob("*.py")
                        if p.stem != "__init__"})
    (out / "sitecheck" / "severity.py").write_text(
        solved_severity(all_names), encoding="utf-8")
    (out / "sitecheck" / "report.py").write_text(
        solved_report(as_list), encoding="utf-8")
    (out / "docs" / "decisions.md").write_text(
        decisions_for(items, solved, as_list), encoding="utf-8")

    # 보이는 테스트는 시작 상태의 기대값을 담고 있다. 해답에서는 다시 쓴다 —
    # 세션도 항목을 옮기면서 같은 일을 한다.
    (out / "tests" / "test_visible.py").write_text("\n".join([
        '"""보이는 테스트."""',
        "",
        "from sitecheck.legacy_registry import LEGACY_CHECKS",
        "from sitecheck.registry import CHECKS",
        "",
        "",
        "def test_no_check_is_registered_twice():",
        "    assert not (set(LEGACY_CHECKS) & set(CHECKS))",
        "",
        "",
        "def test_every_registered_check_runs():",
        "    for name, func in CHECKS.items():",
        "        assert func({'x': 'ok'}) is not None, name",
        "",
    ]), encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) < 3:
        print("사용: queue_solve.py <과제 이름> <목록|건수> <나갈 자리>"
              " [--upto qNN]")
        return 1
    upto = None
    if "--upto" in args:
        index = args.index("--upto")
        upto = args[index + 1]
        args = args[:index] + args[index + 2:]
    root = solve(args[0], args[1], Path(args[2]), upto)
    print(f"{args[0]} {args[1]}: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
