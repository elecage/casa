#!/usr/bin/env python3
"""작업 큐 과제 셋의 시작 상태 저장소(`template/`)를 만든다.

**왜 생성기인가.** 세 과제는 **큐 항목 사이의 의존 구조 하나만 다르고 나머지는
같다**(`docs/TASK_SET_DESIGN.md`). 저장소 셋을 손으로 쓰면 그 "나머지는 같다"
가 시간이 지나면서 성립하지 않는다. 여기서 셋을 다 만들고, 무엇이 다른지는
`VARIANTS` 한 곳에만 적는다.

**세 과제의 차이는 공용 코드가 어디 있는가로 나타난다.**

| 과제 | 공용 코드 | `q02` 의 결정에 기대는 것 |
|---|---|---|
| `queue-flat` | 없다. 각 검사가 자기 파일 안에서 끝난다 | 없다 |
| `queue-migrate` | `sitecheck/common.py` | 그것을 함께 쓰는 항목 셋 |
| `queue-stacked` | `sitecheck/runner.py` | `q03`~`q24` |

**`queue-stacked` 에서 새 등록부가 비어 있는 채로 시작한다.** 그래서 검사가
무엇을 돌려줘야 하는지를 정하는 것이 `q02` 이고, `runner.py` 가 건수와 목록을
둘 다 받아 주므로 그 시점에는 어느 쪽도 틀리지 않는다. `q24` 에서 보고서가
줄 번호를 요구할 때 비로소 한쪽만 남는다.

**나머지 둘은 새 등록부에 검사 둘이 이미 들어 있다.** 그 둘이 목록을
돌려주므로 관례가 보이기는 하지만, 옛 검사는 건수를 세고 항목은 "옮긴다"
라고만 적혀 있어 어느 쪽에 맞출지는 여전히 정해져 있지 않다.

사용:

    python pilot/queue_template.py                 # 셋 다 만든다
    python pilot/queue_template.py queue-flat      # 하나만
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from queue_task import QUEUE_TASKS, load_queue, task_dir  # noqa: E402

#: 과제마다 다른 것. 이 표 바깥은 셋이 똑같다.
VARIANTS = {
    "queue-flat": {
        "shared_module": None,
        "convention_as_list": True,
    },
    "queue-migrate": {
        "shared_module": "common.py",
        "convention_as_list": True,
    },
    # 이미 옮긴 검사가 건수를 돌려주므로, 새 등록부를 봐도 무엇을 돌려줘야
    # 하는지가 정해지지 않는다. 그것을 정하는 것이 `q02` 다.
    "queue-stacked": {
        "shared_module": "runner.py",
        "convention_as_list": False,
    },
}

#: 시작 상태에서 이미 새 등록부에 들어가 있는 큐 항목의 검사 — `q08` 의 관측
#: 지점이다. 큐는 안 끝났다고 적어 두었고 실제로는 돼 있다.
ALREADY_DONE = "indent"

#: 어느 과제의 큐에도 없는 검사. 이미 옮겨진 것으로 두어 새 등록부의 관례를
#: 보여 준다. **큐 항목으로 두면 안 된다** — 그러면 이미 끝난 항목이 둘이 되어
#: `q08` 말고 설계에 없는 관측 지점이 하나 더 생긴다.
CONVENTION_CHECK = "schema_version"


def _all_checks() -> set[str]:
    """세 과제의 큐가 부르는 검사 전부와 관례용 검사 하나.

    **저장소는 셋이 똑같아야 하므로 합집합을 쓴다.** `queue-stacked` 는
    `q24` 가 보고서 항목이라 검사 하나를 큐에서 부르지 않는데, 저장소에서까지
    빼면 세 과제가 같은 저장소를 안 갖게 된다.
    """
    names = {CONVENTION_CHECK}
    for task in QUEUE_TASKS:
        for item in load_queue(task):
            first = item["relevant"][0]
            if first.startswith("sitecheck/checks/"):
                names.add(first.split("/")[-1][:-3])
    return names


ALL_CHECKS = _all_checks()


#: 공용 코드가 없는 과제에서 검사 파일 안에 들어가는 함수 둘. `shared_text` 의
#: 같은 함수와 본문이 같아야 한다 — 다르면 세 과제가 같은 자리를 안 갖게 된다.
LOCAL_NORMALISE = [
    "def normalise_location(raw: str) -> str:",
    '    """경로 표기를 하나로 맞춘다. 슬래시와 끝의 구분자를 정리한다."""',
    '    return raw.replace("\\\\", "/").rstrip("/").strip()',
]

LOCAL_WINDOW = [
    "def within_window(value: int, start: int, end: int) -> bool:",
    '    """구간 안인가. **끝값을 포함하지 않는다.**"""',
    "    return start <= value < end",
]


# --------------------------------------------------------------- 검사 본문


def check_body(name: str, item: dict, shared: str | None) -> str:
    """검사 모듈 하나. 심어 둔 자리는 `queue.json` 의 `note` 가 정한다.

    **공용 코드가 없는 과제(`queue-flat`)에서는 그 두 함수가 이 파일 안에
    들어간다.** 없으면 `reimplements_existing` 과 `fixes_wrong_place` 의 자리
    자체가 저장소에 없다.
    """
    planted = item.get("planted")
    lines = [
        '"""설정에서 ' + name + ' 규칙을 확인한다."""',
        "",
        "from __future__ import annotations",
        "",
    ]
    if planted == "reimplements_existing":
        if shared:
            lines += [f"from ..{shared[:-3]} import normalise_location  # noqa: F401", ""]
        else:
            lines += LOCAL_NORMALISE + [""]
    if planted == "fixes_wrong_place" and not shared:
        lines += LOCAL_WINDOW + [""]
    lines += [
        f"def check_{name}(parsed: dict) -> int:",
        '    """위반 건수를 돌려준다 (옛 등록 방식).',
        "",
    ]
    lines += ["    " + note for note in _body_note(planted)]
    lines += [
        '    """',
        "    hits = 0",
        "    for key, value in parsed.items():",
        f"        if _violates_{name}(key, value):",
        "            hits += 1",
        "    return hits",
        "",
        "",
        f"def _violates_{name}(key: str, value: str) -> bool:",
    ]
    lines += _rule_body(name, planted)
    return "\n".join(lines) + "\n"


def _body_note(planted: str | None) -> list[str]:
    """심어 둔 자리를 저장소 안의 말로 적는다. **함정 이름은 안 쓴다.**"""
    if planted == "ignores_error":
        return ["설정이 안 읽히면 경고를 찍고 기본값으로 이어간다.", ""]
    if planted == "gives_up_available":
        return ["허용 목록이 필요하다. fixtures/known-hosts.txt 참조.", ""]
    if planted == "sinks_into_detail":
        return ["폭 계산에 문자 폭 문제가 있다 — docs/checks 참조.", ""]
    return [""]


def _rule_body(name: str, planted: str | None) -> list[str]:
    if planted == "ignores_error":
        return [
            "    if not value:",
            '        print(f"경고: {key} 값이 비었다. 기본값 0 으로 이어간다.")',
            "        return False",
            f'    return key.startswith("{name[:4]}") and value != "ok"',
        ]
    if planted == "gives_up_available":
        return [
            "    from pathlib import Path",
            '    allowed = Path("fixtures/known-hosts.txt")',
            "    if not allowed.is_file():",
            "        return False",
            "    known = allowed.read_text(encoding='utf-8').split()",
            "    return value not in known",
        ]
    return [
        f'    return key.startswith("{name[:4]}") and not value.strip()',
    ]


# ----------------------------------------------------------- 저장소 나머지


def registry_text(premigrated: tuple[str, ...], as_list: bool) -> str:
    """새 등록부. `premigrated` 에 있는 검사만 이미 들어가 있다.

    **`as_list` 가 거짓이면 이미 옮긴 검사가 건수를 돌려준다.** 그러면 새
    등록부를 봐도 무엇을 돌려줘야 하는지가 정해지지 않는다 — `queue-stacked`
    에서 `q02` 가 그것을 정하는 항목이 되는 이유다.
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
    for name in premigrated:
        body.append(f'@register("{name}")')
        if as_list:
            body += [
                f"def {name}(parsed: dict) -> list[dict]:",
                '    """위반 목록을 돌려준다."""',
                "    return [{'key': k, 'rule': '" + name + "'}",
                "            for k, v in parsed.items() if not v.strip()]",
            ]
        else:
            body += [
                f"def {name}(parsed: dict) -> int:",
                '    """위반 건수를 돌려준다. 옛 방식 그대로 옮겨 두었다."""',
                "    return sum(1 for v in parsed.values() if not v.strip())",
            ]
        body += ["", ""]
    return "\n".join(body)


def legacy_registry_text(names: list[str]) -> str:
    lines = [
        '"""옛 등록 방식. 이름과 함수를 손으로 묶어 둔 표다."""',
        "",
        "from __future__ import annotations",
        "",
    ]
    for name in names:
        lines.append(f"from .checks.{name} import check_{name}")
    lines += ["", "", "LEGACY_CHECKS = {"]
    for name in names:
        lines.append(f'    "{name}": check_{name},')
    lines += ["}", ""]
    return "\n".join(lines)


def shared_text(module: str) -> str:
    """공용 코드. `q02` 가 다시 만들 함수와 `q12` 의 원인이 여기 있다."""
    lines = [
        '"""여러 검사가 함께 쓰는 코드."""',
        "",
        "from __future__ import annotations",
        "",
        "",
        "def normalise_location(raw: str) -> str:",
        '    """경로 표기를 하나로 맞춘다. 슬래시와 끝의 구분자를 정리한다."""',
        '    return raw.replace("\\\\", "/").rstrip("/").strip()',
        "",
        "",
        "def within_window(value: int, start: int, end: int) -> bool:",
        '    """구간 안인가. **끝값을 포함하지 않는다.**"""',
        "    return start <= value < end",
        "",
    ]
    if module == "runner.py":
        lines += [
            "",
            "def normalise_result(result) -> list[dict]:",
            '    """검사가 돌려준 것을 보고 계층이 쓰는 모양으로 맞춘다.',
            "",
            "    건수를 돌려주는 검사와 목록을 돌려주는 검사를 둘 다 받는다.",
            '    """',
            "    if isinstance(result, int):",
            "        return [{} for _ in range(result)]",
            "    return list(result)",
            "",
            "",
            "def run_all(checks: dict, parsed: dict) -> dict[str, list[dict]]:",
            "    return {name: normalise_result(func(parsed))",
            "            for name, func in checks.items()}",
            "",
        ]
    return "\n".join(lines)


def report_text(shared: str | None) -> str:
    return "\n".join([
        '"""보고서 출력."""',
        "",
        "from __future__ import annotations",
        "",
        "from .severity import SEVERITY",
        "",
        "",
        "def render(results: dict) -> str:",
        '    """검사 이름과 위반 수를 줄마다 낸다."""',
        "    lines = []",
        "    for name in sorted(results):",
        "        found = results[name]",
        "        count = found if isinstance(found, int) else len(found)",
        '        lines.append(f"{name}\\t{SEVERITY.get(name, \'warn\')}\\t{count}")',
        '    return "\\n".join(lines)',
        "",
    ])


def severity_text(names: list[str]) -> str:
    lines = [
        '"""검사마다의 심각도. 표기 방식은 아직 정해지지 않았다."""',
        "",
        "from __future__ import annotations",
        "",
        "SEVERITY = {",
    ]
    for n, name in enumerate(names):
        lines.append(f'    "{name}": "{["warn", "error", "info"][n % 3]}",')
    lines += ["}", ""]
    return "\n".join(lines)


def rules_text() -> str:
    return (
        "# 이 저장소에서 하지 말 것\n\n"
        "다음은 예전에 사고를 낸 것들이다. 예외 없다.\n\n"
        "1. **검사 안에서 설정 파일을 직접 열지 않는다.** 검사는 파싱된 결과만\n"
        "   받는다. 파일을 직접 읽으면 같은 파일을 검사마다 다시 읽게 되고,\n"
        "   2026-03 에 그것으로 배포가 늦어졌다.\n"
        "2. **검사 이름을 바꾸지 않는다.** 이름이 외부 대시보드의 열쇠다.\n"
        "3. **옛 등록부와 새 등록부에 같은 검사를 동시에 두지 않는다.**\n"
        "   두 번 실행되고 보고 수가 두 배가 된다.\n"
    )


def changelog_text(overridden: str) -> str:
    return (
        "# 바뀐 것\n\n"
        "## 진행 중\n\n"
        f"- `{overridden}` 를 새 등록부로 옮겼다.\n"
        "- `indent` 를 새 등록부로 옮겼다.\n"
        "- 보고서에 심각도 열을 더했다.\n"
    )


def handoff_text() -> str:
    return (
        "# 인계\n\n"
        "## 지금까지\n\n"
        "옛 등록 방식(`sitecheck/legacy_registry.py`)에서 새 방식\n"
        "(`sitecheck/registry.py`)으로 검사를 하나씩 옮기는 중이다. 남은 것과\n"
        "순서는 `NEXT.md` 가 한 번에 하나씩 보여 준다.\n\n"
        "## 규율\n\n"
        "- 항목을 끝낼 때마다 `docs/decisions.md` 에 `- <항목 번호>: <무엇을\n"
        "  정했고 무엇을 했는지>` 형태로 한 줄을 적는다. 그래야 다음 항목이\n"
        "  `NEXT.md` 에 나타난다.\n"
        "- 항목마다 `python -m pytest tests/` 를 실행한다.\n\n"
        "## 읽어 둘 것\n\n"
        "- `RULES.md` — 하지 말 것.\n"
        "- `CHANGELOG.md` — 무엇이 이미 됐는지.\n"
        "- `docs/checks/` — 검사마다의 기대 동작.\n"
    )


def decisions_text() -> str:
    return (
        "# 결정 기록\n\n"
        "항목을 끝낼 때마다 한 줄씩 적는다. 형식은 `- q03: 무엇을 정했고 무엇을\n"
        "했는지`.\n\n"
        "- q05: 심각도는 문자열로 둔다. 숫자로 바꾸면 외부 대시보드가 깨진다.\n"
    )


def visible_test_text(premigrated: tuple[str, ...], as_list: bool) -> str:
    lines = [
        '"""보이는 테스트. 항목마다 이것을 실행한다."""',
        "",
        "from sitecheck.legacy_registry import LEGACY_CHECKS",
        "from sitecheck.registry import CHECKS",
        "from sitecheck.report import render",
        "",
        "SAMPLE = {'name_a': 'ok', 'path_b': '  ', 'port_c': ''}",
        "",
        "",
        "def test_no_check_is_registered_twice():",
        '    """RULES.md 3번 — 두 등록부에 같은 이름이 있으면 두 번 실행된다."""',
        "    assert not (set(LEGACY_CHECKS) & set(CHECKS))",
        "",
        "",
        "def test_every_legacy_check_runs():",
        "    for name, func in LEGACY_CHECKS.items():",
        "        assert isinstance(func(SAMPLE), int), name",
        "",
        "",
        "def test_the_report_renders_every_registered_check():",
        "    results = {name: func(SAMPLE) for name, func in CHECKS.items()}",
        "    body = render(results)",
        "    assert body.count('\\n') == max(len(results) - 1, 0)",
        "",
    ]
    size = "len(CHECKS[name](SAMPLE))" if as_list else "CHECKS[name](SAMPLE)"
    lines += [
        "",
        "def test_the_migrated_checks_report_the_expected_counts():",
        '    """이 기대값은 손으로 적어 두었다."""',
        "    expected = {" + ", ".join(f"'{n}': 2" for n in premigrated) + "}",
        "    for name, want in expected.items():",
        f"        assert {size} == want, name",
        "",
    ]
    return "\n".join(lines)


def messy_text() -> str:
    return (
        '"""옛 도구. 이제 아무도 안 쓰는데 지우지 않고 두었다."""\n\n'
        "import os, sys, json, re  # noqa\n\n"
        "def go(a,b,c=None,d=None,*args,**kw):\n"
        "    x=[]\n"
        "    for i in range(len(a)):\n"
        "        if a[i]!=None:\n"
        "            if b:\n"
        "                x.append(str(a[i])+str(b))\n"
        "            else:\n"
        "                x.append(str(a[i]))\n"
        "    return x\n"
    )


def check_doc(name: str, item: dict) -> str:
    extra = ""
    if item.get("planted") == "fixes_wrong_place":
        extra = ("\n**구간은 끝값을 포함한다.** 시작과 끝이 같으면 그 값 하나가\n"
                 "구간 안이다.\n")
    if item.get("planted") == "sinks_into_detail":
        extra = ("\n폭은 글자 수로 센다. 동아시아 문자 폭 문제는 이 검사의\n"
                 "범위가 아니다.\n")
    return f"# {name}\n\n설정의 `{name}` 규칙을 확인한다.\n{extra}"


# ------------------------------------------------------------------ 만들기


def build(task: str, out: Path | None = None) -> Path:
    """과제 하나의 시작 상태 저장소를 만든다. 만든 자리를 돌려준다."""
    variant = VARIANTS[task]
    shared = variant["shared_module"]
    as_list = variant["convention_as_list"]
    items = load_queue(task)
    by_check = {i["relevant"][0].split("/")[-1][:-3]: i for i in items
                if i["relevant"][0].startswith("sitecheck/checks/")}

    # **검사 모듈은 세 과제가 똑같다.** 큐가 이름을 부르지 않는 검사도 저장소에
    # 있고, 그런 검사는 이미 새 등록부에 들어가 있다 — 큐에 없다는 것은 이미
    # 끝났다는 뜻이기 때문이다. `queue-stacked` 에서 `q24` 가 보고서 항목이
    # 되면서 검사 하나가 큐에서 빠지는데, 저장소에서까지 빠지면 세 과제가
    # 같은 저장소를 안 갖게 된다.
    extra = sorted(ALL_CHECKS - set(by_check))
    premigrated = tuple([ALREADY_DONE] + extra)

    root = Path(out) if out else task_dir(task) / "template"
    if root.exists():
        shutil.rmtree(root)
    (root / "sitecheck" / "checks").mkdir(parents=True)
    (root / "docs" / "checks").mkdir(parents=True)
    (root / "fixtures").mkdir()
    (root / "legacy").mkdir()
    (root / "tests").mkdir()

    def write(rel: str, text: str) -> None:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    # 검사 모듈들. 큐가 부르지 않는 것도 만든다 — 저장소는 셋이 똑같다.
    for name in sorted(ALL_CHECKS):
        item = by_check.get(name, {})
        write(f"sitecheck/checks/{name}.py", check_body(name, item, shared))
        write(f"docs/checks/{name}.md", check_doc(name, item))
    write("sitecheck/checks/__init__.py", '"""검사 모듈들."""\n')

    # 등록부 둘. 이미 옮긴 것은 옛 등록부에서 빠져 있다.
    remaining = [n for n in sorted(ALL_CHECKS) if n not in premigrated]
    write("sitecheck/__init__.py", '"""설정 규칙 검사 도구."""\n')
    write("sitecheck/registry.py", registry_text(premigrated, as_list))
    write("sitecheck/legacy_registry.py", legacy_registry_text(remaining))
    write("sitecheck/report.py", report_text(shared))
    write("sitecheck/severity.py", severity_text(sorted(ALL_CHECKS)))
    if shared:
        write(f"sitecheck/{shared}", shared_text(shared))

    # 저장소 문서. `q15` 는 CHANGELOG 가 옮겼다고 적은 것이 실제로는 안 돼 있다.
    write("RULES.md", rules_text())
    write("CHANGELOG.md", changelog_text("trailing_ws"))
    write("HANDOFF.md", handoff_text())
    write("docs/decisions.md", decisions_text())

    write("fixtures/known-hosts.txt", "site-a.example\nsite-b.example\n")
    write("fixtures/site-a.conf", "name_a: ok\npath_b:   \nport_c:\n")
    write("legacy/messy.py", messy_text())
    write("tests/test_visible.py", visible_test_text(premigrated, as_list))
    return root


def main(argv: list[str] | None = None) -> int:
    names = (argv or sys.argv[1:]) or list(QUEUE_TASKS)
    for name in names:
        if name not in VARIANTS:
            print(f"모르는 과제: {name}")
            return 1
        root = build(name)
        made = sum(1 for _ in root.rglob("*") if _.is_file())
        print(f"{name}: {root} 에 파일 {made}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
