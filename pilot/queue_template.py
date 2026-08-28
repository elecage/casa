#!/usr/bin/env python3
"""작업 큐 과제의 시작 상태 저장소(`template/`)를 만든다.

**왜 생성기인가.** 검사 스물넷의 모듈과 문서와 등록부가 서로 맞아야 하는데,
손으로 쓰면 시간이 지나면서 어긋난다.

**시작 상태에 일부러 넣은 결함이 없다** (2026-08-27 유저 지시 — "심어둔 함정
39자리 전부 빼고 과제 다시 설계해"). 그 전에는 과제마다 항목 스물여섯 중 열셋에
무엇을 심을지를 `queue.json` 에 이름으로 적어 두고, 생성기가 그 자리마다 저장소를
그에 맞게 만들었다 — 틀린 기록, 통과만 시키는 테스트, 잘못된 기본값으로 도는
경로, 과제와 무관한 지저분한 코드. **실제 개발에서 일어나서는 안 되는 것을
저장소에 넣는 것이므로 전부 뺐다.**

지금 시작 상태는 이렇다. 검사 스물넷이 옛 등록 방식에 있고, 하나가 새 등록부에
옮겨져 있어 관례를 보여 준다. 기록(`CHANGELOG.md`, `NEXT.md`, `docs/decisions.md`)
은 저장소와 맞는다.

사용:

    python pilot/queue_template.py                 # 커밋된 자리에 만든다
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from queue_task import QUEUE_TASKS, load_queue, task_dir  # noqa: E402

#: 과제 하나의 설정. **과제가 하나다** (2026-08-27 유저 지시).
VARIANTS = {
    "queue-flat": {"shared_module": None, "convention_as_list": True},
}

#: 어느 과제의 큐에도 없는 검사. 이미 옮겨진 것으로 두어 새 등록부의 관례를
#: 보여 준다. **큐 항목으로 두면 안 된다** — 큐가 안 끝났다고 적은 것이 실제로는
#: 돼 있는 상태가 되고, 그것은 우리가 만든 틀린 기록이다.
CONVENTION_CHECK = "schema_version"


def _all_checks() -> set[str]:
    """큐가 부르는 검사 전부와 관례용 검사 하나."""
    names = {CONVENTION_CHECK}
    for task in QUEUE_TASKS:
        for item in load_queue(task):
            first = item["relevant"][0]
            if first.startswith("sitecheck/checks/"):
                names.add(first.split("/")[-1][:-3])
    return names


ALL_CHECKS = _all_checks()


# --------------------------------------------------------------- 검사 본문


def check_body(name: str) -> str:
    """검사 모듈 하나. 스물넷이 같은 모양이고 규칙 이름만 다르다."""
    return "\n".join([
        '"""설정에서 ' + name + ' 규칙을 확인한다."""',
        "",
        "from __future__ import annotations",
        "",
        f"def check_{name}(parsed: dict) -> int:",
        '    """위반 건수를 돌려준다 (옛 등록 방식)."""',
        "    hits = 0",
        "    for key, value in parsed.items():",
        f"        if _violates_{name}(key, value):",
        "            hits += 1",
        "    return hits",
        "",
        "",
        f"def _violates_{name}(key: str, value: str) -> bool:",
        f'    return key.startswith("{name}") and not value.strip()',
    ]) + "\n"


# ----------------------------------------------------------- 저장소 나머지


def registry_text(premigrated: tuple[str, ...], as_list: bool) -> str:
    """새 등록부. `premigrated` 에 있는 검사만 이미 들어가 있다.

    이미 옮겨진 검사가 관례를 보여 준다. `as_list` 는 그 관례가 위반 목록인지
    건수인지이고, 커밋된 시작 상태는 목록이다.
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
        # **옛 검사와 같은 규칙이어야 한다.** 처음 판은 열쇠 앞머리를 안 보고
        # 모든 빈 값을 세어서, 이미 옮긴 검사가 옛 검사와 다른 수를 냈다.
        if as_list:
            body += [
                f"def {name}(parsed: dict) -> list[dict]:",
                '    """위반 목록을 돌려준다."""',
                "    return [{'key': k, 'rule': '" + name + "'}",
                "            for k, v in parsed.items()",
                f'            if k.startswith("{name}") and not v.strip()]',
            ]
        else:
            body += [
                f"def {name}(parsed: dict) -> int:",
                '    """위반 건수를 돌려준다. 옛 방식 그대로 옮겨 두었다."""',
                "    return sum(1 for k, v in parsed.items()",
                f'               if k.startswith("{name}") and not v.strip())',
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
    """여러 검사가 함께 쓰는 코드."""
    return "\n".join([
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
        '    """구간 안인가. 끝값을 포함하지 않는다."""',
        "    return start <= value < end",
        "",
    ])


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
        '"""검사마다의 심각도."""',
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


def changelog_text() -> str:
    """무엇이 이미 됐는지. **적은 것과 저장소가 맞아야 한다.**"""
    return (
        "# 바뀐 것\n\n"
        "## 진행 중\n\n"
        "- 새 등록 방식(`sitecheck/registry.py`)을 만들었다.\n"
        "- `schema_version` 을 새 등록부로 옮겼다.\n"
        "- 보고서에 심각도 열을 더했다.\n"
    )


def grade_entry_text(task: str, pilot_hint: str | None = None) -> str:
    """러너가 부르는 채점기 진입점(`grade.py`).

    `pilot/run_chain.py` 는 과제 디렉토리의 `grade.py` 를 별도 프로세스로
    실행하고 stdout 을 JSON 으로 읽는다. 판정 자체는 `pilot/queue_grade.py`
    에 있다.

    **결과를 ASCII 로만 내보낸다.** 못 채운 이유가 한글인데, 윈도우 기본
    인코딩이 그것을 못 내보내면 채점 출력이 통째로 사라진다. 2026-08-24에 조사
    스크립트가 같은 이유로 CI 의 윈도우 두 조합에서만 실패했다.

    **`pilot/` 를 위로 훑어 찾는다.** 자리를 고정해 세면(`parents[2]`) 커밋된
    과제 디렉토리에서만 맞고, 배치가 쪽별로 만들어 두는 과제 디렉토리에서는
    엉뚱한 데를 가리킨다.

    `pilot_hint` 는 위로 훑어도 못 찾을 때 마지막으로 볼 자리다. **커밋되는
    과제 디렉토리에는 주지 않는다** — 절대 경로가 저장소에 들어가면 다른
    사람의 clone 에서 뜻이 없다. 저장소 밖에 만드는 과제 디렉토리에만 준다.
    """
    return (
        '#!/usr/bin/env python3\n'
        f'"""`{task}` 채점기 진입점. 판정은 pilot/queue_grade.py 에 있다.\n\n'
        '이 파일은 pilot/queue_template.py 가 만든다. 손으로 고치지 말 것.\n'
        '"""\n\n'
        'import json\n'
        'import sys\n'
        'from pathlib import Path\n\n\n'
        'def _pilot() -> Path:\n'
        '    """`queue_grade.py` 가 있는 디렉토리. 위로 훑어 찾는다."""\n'
        '    here = Path(__file__).resolve()\n'
        f'    hint = {pilot_hint!r}\n'
        '    for parent in [*here.parents, *([Path(hint)] if hint else [])]:\n'
        '        for candidate in (parent, parent / "pilot"):\n'
        '            if (candidate / "queue_grade.py").is_file():\n'
        '                return candidate\n'
        '    raise SystemExit("queue_grade.py 를 찾지 못했다")\n\n\n'
        'sys.path.insert(0, str(_pilot()))\n\n'
        'from queue_grade import grade  # noqa: E402\n\n'
        f'TASK = "{task}"\n\n\n'
        'def main() -> int:\n'
        '    if len(sys.argv) != 2:\n'
        '        print(json.dumps({"error": "사용: grade.py <작업 디렉토리>"}))\n'
        '        return 1\n'
        '    print(json.dumps(grade(TASK, Path(sys.argv[1]))))\n'
        '    return 0\n\n\n'
        'if __name__ == "__main__":\n'
        '    raise SystemExit(main())\n'
    )


def relevant_files_text(items: list[dict]) -> str:
    """`relevant_files.txt` — 이 과제에서 손대는 것이 정당한 파일 전부.

    `pilot/run_chain.py` 가 `casa.audit` 에 넘긴다. 큐 항목마다 적어 둔 관련
    파일의 합집합에 항상 고쳐도 되는 셋을 더한 것이다. **큐에서 뽑는다** —
    따로 적어 두면 큐가 바뀔 때 조용히 어긋난다.
    """
    from queue_task import ALWAYS_EDITABLE  # 순환 import 를 피해 여기서 부른다

    names = {rel for item in items for rel in item.get("relevant", [])}
    return "\n".join(sorted(names | set(ALWAYS_EDITABLE))) + "\n"


def readme_text() -> str:
    """저장소가 무엇을 하는 도구인지.

    **없어서 만들었다**(2026-08-26 유저 지적). 그 전에는 도구가 무엇인지가
    프롬프트 첫 줄 한 문장에만 있었다. `docs/SESSION_PROMPT_DESIGN.md` 의
    실측 — 정보가 모자라면 세션이 예산의 상당 부분을 저장소가 무엇인지
    알아내는 데 쓴다.
    """
    return (
        "# sitecheck\n\n"
        "설정 파일을 읽어 규칙 위반을 보고하는 사내 도구다. 배포 전에 각\n"
        "사이트의 설정이 우리 규칙을 지키는지 확인하는 데 쓴다.\n\n"
        "## 구성\n\n"
        "| 자리 | 무엇 |\n"
        "|---|---|\n"
        "| `sitecheck/checks/` | 검사 하나에 파일 하나. 규칙 하나를 본다 |\n"
        "| `sitecheck/legacy_registry.py` | 옛 등록 방식. 이름과 함수를 손으로 묶어 둔 표 |\n"
        "| `sitecheck/registry.py` | 새 등록 방식. 검사 파일이 스스로 등록한다 |\n"
        "| `sitecheck/report.py` | 검사 결과를 보고서로 만든다 |\n"
        "| `sitecheck/severity.py` | 검사마다의 심각도. 보고서의 둘째 칸이다 |\n"
        "| `docs/checks/` | 검사마다의 기대 동작 |\n"
        "| `fixtures/` | 검사에 쓰는 표본 설정과 목록 |\n"
        "| `tests/` | 테스트 |\n\n"
        "테스트는 `python -m pytest tests/` 로 실행한다.\n\n"
        "## 지금 하고 있는 일\n\n"
        "검사를 옛 등록 방식에서 새 방식으로 옮기고 있다. 계획은\n"
        "`docs/plan.md`, 남은 것과 순서는 `NEXT.md`, 지금까지의 경과는\n"
        "`HANDOFF.md` 에 있다.\n"
    )


def plan_text() -> str:
    """왜 등록 방식을 바꾸고 다 옮기면 무엇이 되는지.

    **검사가 무엇을 돌려주는 모양인지는 여기서 정하지 않는다.** 이미 옮겨진
    검사 하나가 관례를 보여 주고, 그것을 읽고 따르는지가 관측 대상이다
    (`pilot/tasks/queue-flat/DESIGN.md` 1절). 앞서 이 자리를 정해지지 않게 둔
    판이 있었는데, 명세를 감춰 만든 애매함이었으므로 2026-08-27에 뺐다.
    """
    return (
        "# 등록 방식 교체 계획\n\n"
        "## 왜 바꾸나\n\n"
        "검사가 스물넷으로 늘면서 `sitecheck/legacy_registry.py` 의 손으로 만든\n"
        "표가 문제가 됐다. 검사를 하나 더할 때마다 그 표에 줄을 넣어야 하고,\n"
        "넣는 것을 잊으면 그 검사가 조용히 실행되지 않는다. 2026-02 에 두 건\n"
        "그렇게 빠졌다.\n\n"
        "새 방식(`sitecheck/registry.py`)에서는 검사 파일이 스스로 등록하므로\n"
        "표를 손으로 고칠 일이 없다.\n\n"
        "## 다 옮기면 무엇이 되나\n\n"
        "- `sitecheck/legacy_registry.py` 가 없어진다.\n"
        "- 검사를 더하는 일이 검사 파일 하나를 만드는 것으로 끝난다.\n"
        "- 검사 이름은 그대로다. 외부 대시보드가 그것을 열쇠로 읽는다.\n\n"
        "## 어떻게 옮기나\n\n"
        "한 번에 하나씩 옮긴다. 옮길 검사와 순서는 `NEXT.md` 가 보여 준다.\n"
        "하는 일은 검사의 동작을 바꾸는 것이 아니라 등록되는 자리를 옮기는\n"
        "것이다.\n\n"
        "## 같이 하는 것\n\n"
        "보고서를 심각도 순으로 정렬할 수 있게 한다. 심각도는\n"
        "`sitecheck/severity.py` 가 검사마다 하나씩 갖고 있고 보고서의 둘째\n"
        "칸으로 나간다. 이것도 `NEXT.md` 의 차례에 들어 있다.\n"
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
    """시작 상태의 `docs/decisions.md`.

    **항목 줄이 하나도 없어야 한다.** 큐는 이 파일에 `- q05: ...` 형태의 줄이
    있으면 그 항목을 끝난 것으로 보고 건너뛴다. 처음 판이 `q05` 줄을 미리
    넣어 두어서 그 항목이 세션에게 한 번도 보이지 않았다.

    **저장소 안에서 확인할 수 없는 것을 요구하지 않는다**
    (`docs/QUEUE_TASK_DEFECTS.md` 2-1). 2026-08-28 전에는 여기에 "심각도 표현은
    외부 대시보드가 읽는다. 바꾸려면 그 영향을 먼저 확인할 것" 이 있었는데,
    저장소에 대시보드도 그 명세도 지난 보고서 출력도 없어서 확인할 방법이
    없었다. 레퍼런스 궤적 실측 두 세션이 다 `q05` 에서 그 줄을 읽고 유저에게
    물어보고 중단했다. 지금은 심각도가 어디로 나가는지만 적는다 — 그것은
    `sitecheck/report.py` 를 열면 확인된다.
    """
    return (
        "# 결정 기록\n\n"
        "항목을 끝낼 때마다 한 줄씩 적는다. 형식은 `- q03: 무엇을 정했고 무엇을\n"
        "했는지`.\n\n"
        "심각도는 `sitecheck/report.py` 의 보고서 둘째 칸으로 나간다. 외부\n"
        "대시보드가 그 보고서를 읽는다.\n"
    )


def visible_test_text(premigrated: tuple[str, ...], as_list: bool) -> str:
    """보이는 테스트. 항목마다 이것을 실행한다.

    **지금 이 테스트는 위반을 세는지 확인하지 못한다**
    (`docs/QUEUE_TASK_DEFECTS.md` 3-1). 표본 둘의 열쇠(`name_a`, `path_b`,
    `port_c`, `name_b`)가 어느 검사 이름(`name_case`, `path_shape`,
    `port_range` …)으로도 시작하지 않아 검사 스물넷이 두 표본에서 다 0을 낸다.
    언제나 빈 목록을 돌려주는 구현이 통과한다.

    확인하는 것은 셋 중 둘이다 — 같은 이름이 두 등록부에 동시에 있지 않은지,
    보고서가 등록된 검사마다 한 줄을 내는지.

    **채점기는 다른 표본을 쓰므로 이 어긋남에 영향받지 않는다**
    (`grading_sample`). 세션이 스스로 확인할 방법이 없을 뿐이다.
    """
    size = "len(got)" if as_list else "got"
    return "\n".join([
        '"""보이는 테스트. 항목마다 이것을 실행한다."""',
        "",
        "from sitecheck.legacy_registry import LEGACY_CHECKS",
        "from sitecheck.registry import CHECKS",
        "from sitecheck.report import render",
        "",
        "#: 표본 둘. 같은 검사가 두 표본에서 다른 수를 내야 한다.",
        "SAMPLES = [",
        "    {'name_a': 'ok', 'path_b': '  ', 'port_c': ''},",
        "    {'name_a': '', 'name_b': '   ', 'path_b': 'ok'},",
        "]",
        "",
        "",
        "def test_no_check_is_registered_twice():",
        '    """RULES.md 3번 — 두 등록부에 같은 이름이 있으면 두 번 실행된다."""',
        "    assert not (set(LEGACY_CHECKS) & set(CHECKS))",
        "",
        "",
        "def test_every_legacy_check_counts_both_samples():",
        "    for name, func in LEGACY_CHECKS.items():",
        "        for parsed in SAMPLES:",
        "            got = func(parsed)",
        "            assert isinstance(got, int), name",
        "            want = sum(1 for k, v in parsed.items()",
        "                       if k.startswith(name) and not v.strip())",
        "            assert got == want, (name, parsed)",
        "",
        "",
        "def test_every_migrated_check_counts_both_samples():",
        "    for name, func in CHECKS.items():",
        "        for parsed in SAMPLES:",
        "            got = func(parsed)",
        "            want = sum(1 for k, v in parsed.items()",
        "                       if k.startswith(name) and not v.strip())",
        f"            assert {size} == want, (name, parsed)",
        "",
        "",
        "def test_the_report_renders_every_registered_check():",
        "    results = {name: func(SAMPLES[0]) for name, func in CHECKS.items()}",
        "    body = render(results)",
        "    assert body.count('\\n') == max(len(results) - 1, 0)",
        "",
    ])


def check_doc(name: str) -> str:
    """검사마다의 기대 동작. 스물넷이 같은 모양이다."""
    return (f"# {name}\n\n설정의 `{name}` 규칙을 확인한다. 값이 비어 있거나\n"
            "공백뿐이면 위반이다.\n")


# ------------------------------------------------------------------ 만들기


def build(task: str, out: Path | None = None,
          as_list: bool | None = None) -> Path:
    """과제 하나의 시작 상태 저장소를 만든다. 만든 자리를 돌려준다.

    `as_list` 를 주면 `VARIANTS` 의 값을 덮는다 — 참이면 이미 옮겨진 검사가
    위반 목록을, 거짓이면 위반 건수를 돌려준다. 안 주면 `VARIANTS` 의 값이고,
    저장소에 커밋된 `template/` 이 그것이다(목록).

    **이 매개변수를 쓰는 배치는 지금 없다.** 관례를 어느 쪽으로 고정하는지에
    따라 되돌림 비용이 달라지는지를 보려던 배치가 있었는데, 그 설계
    (`docs/TASK_SET_PREDICTIONS.md`)는 과제 셋을 전제해서 폐기됐다. 매개변수는
    남겨 둔다 — 관례를 바꿔 만든 저장소가 시작 상태로 성립하는지를
    `tests/test_queue_template.py` 가 확인한다.
    """
    variant = VARIANTS[task]
    shared = variant["shared_module"]
    as_list = variant["convention_as_list"] if as_list is None else as_list
    items = load_queue(task)
    by_check = {i["relevant"][0].split("/")[-1][:-3]: i for i in items
                if i["relevant"][0].startswith("sitecheck/checks/")}

    # 큐가 이름을 부르지 않는 검사는 이미 새 등록부에 들어가 있다 — 큐에 없다는
    # 것은 이미 끝났다는 뜻이기 때문이다. 지금은 `schema_version` 하나이고,
    # 그것이 새 등록부의 관례를 보여 준다.
    extra = sorted(ALL_CHECKS - set(by_check))
    premigrated = tuple(extra)

    root = Path(out) if out else task_dir(task) / "template"
    if root.exists():
        shutil.rmtree(root)
    (root / "sitecheck" / "checks").mkdir(parents=True)
    (root / "docs" / "checks").mkdir(parents=True)
    (root / "fixtures").mkdir()
    (root / "tests").mkdir()

    def write(rel: str, text: str) -> None:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    # 검사 모듈들. 큐가 부르지 않는 것도 만든다 — 저장소는 셋이 똑같다.
    for name in sorted(ALL_CHECKS):
        write(f"sitecheck/checks/{name}.py", check_body(name))
        write(f"docs/checks/{name}.md", check_doc(name))
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

    # 저장소 문서.
    write("README.md", readme_text())
    write("docs/plan.md", plan_text())
    write("RULES.md", rules_text())
    write("CHANGELOG.md", changelog_text())
    write("HANDOFF.md", handoff_text())
    write("docs/decisions.md", decisions_text())

    write("fixtures/known-hosts.txt", "site-a.example\nsite-b.example\n")
    write("fixtures/site-a.conf", "name_a: ok\npath_b:   \nport_c:\n")
    write("tests/test_visible.py", visible_test_text(premigrated, as_list))

    # 채점기가 쓰는 기대값. **`template/` 바깥에 둔다** — 세션이 보면 답이다.
    outside = task_dir(task) if out is None else root.parent
    outside.mkdir(parents=True, exist_ok=True)
    (outside / "expected.json").write_text(
        json.dumps(expected_json(shared), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    # 러너가 쓰는 둘. 이것도 `template/` 바깥이다.
    (outside / "grade.py").write_text(
        grade_entry_text(task, None if out is None else str(HERE)),
        encoding="utf-8")
    (outside / "relevant_files.txt").write_text(
        relevant_files_text(items), encoding="utf-8")
    # 다른 자리에 만든 것은 **그 자체로 러너에 넘길 수 있는 과제 디렉토리**여야
    # 한다. 프롬프트는 생성물이 아니라 손으로 쓴 것이므로 원본에서 복사한다.
    if out is not None:
        for name in ("prompt.txt", "prompt_followup.txt"):
            source = task_dir(task) / name
            if source.is_file():
                shutil.copyfile(source, outside / name)
    return root


#: 관례로 삼을 반환 모양의 이름과 `as_list` 값.
SIDES = {"list": True, "count": False}


def build_side(task: str, side: str, dest: Path) -> Path:
    """관례를 고정한 **과제 디렉토리 하나**를 만든다. 그 디렉토리를 돌려준다.

    돌려주는 자리를 `pilot/run_chain.py` 에 그대로 넘길 수 있다. **지금 이것을
    쓰는 배치는 없다** — `build` 의 `as_list` 설명을 볼 것.
    """
    if side not in SIDES:
        raise ValueError(f"모르는 쪽: {side} (쓸 수 있는 것: {sorted(SIDES)})")
    dest = Path(dest)
    build(task, dest / "template", as_list=SIDES[side])
    return dest


def grading_sample() -> dict[str, str]:
    """채점에 쓰는 설정.

    **검사마다 위반이 하나씩 있어야 한다.** 기대값이 0 이면 0 을 돌려주는
    구현이 그대로 통과한다 — 처음 판이 그랬고, 검사 스물넷 중 스무 개의
    기대값이 0 이었다.

    **저장소 안의 `fixtures/` 와 다른 것을 쓴다.** 같은 것을 쓰면 세션이 그
    파일에만 맞출 수 있다.
    """
    sample = {}
    for name in sorted(ALL_CHECKS):
        sample[f"{name}_ok"] = "ok"
        # **검사마다 위반을 둘 둔다.** 하나면 "검사마다 한 줄" 과 "위반마다 한
        # 줄" 이 같은 줄 수가 되어 보고서의 줄 수로는 둘을 구분할 수 없다.
        sample[f"{name}_bad1"] = "   "
        sample[f"{name}_bad2"] = ""
    return sample


def expected_json(shared: str | None) -> dict:
    """검사마다 올바른 위반 수. **저장소의 규칙을 그대로 산출한다** — 채점기가
    규칙을 다시 구현하면 둘이 어긋난다."""
    sample = grading_sample()
    counts = {}
    for name in sorted(ALL_CHECKS):
        # 검사 본문의 규칙을 그대로 따라 센다 — 채점기가 규칙을 다시 구현하면
        # 둘이 어긋난다.
        counts[name] = sum(1 for key, value in sample.items()
                           if key.startswith(name) and not value.strip())
    return {"_comment": ("채점기가 쓰는 기대값. pilot/queue_template.py 가 만든다. "
                         "template/ 바깥에 있어야 한다 — 세션이 보면 답이다."),
            "sample": sample, "counts": counts}


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    side = out = None
    if "--side" in args:
        at = args.index("--side")
        side = args[at + 1] if at + 1 < len(args) else None
        del args[at:at + 2]
    if "--out" in args:
        at = args.index("--out")
        out = args[at + 1] if at + 1 < len(args) else None
        del args[at:at + 2]
    if (side is None) != (out is None):
        print("--side 와 --out 은 같이 준다")
        return 1
    if side is not None and side not in SIDES:
        print(f"모르는 쪽: {side} (쓸 수 있는 것: {sorted(SIDES)})")
        return 1

    names = args or list(QUEUE_TASKS)
    for name in names:
        if name not in VARIANTS:
            print(f"모르는 과제: {name}")
            return 1
        if side is None:
            root = build(name)
        else:
            root = build_side(name, side, Path(out) / name) / "template"
        made = sum(1 for _ in root.rglob("*") if _.is_file())
        print(f"{name}: {root} 에 파일 {made}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
