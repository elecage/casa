#!/usr/bin/env python3
"""손으로 만든 궤적 셋 — 배선이 실제로 이어지는지 확인하는 데 쓴다.

**이것은 실측이 아니다.** 진짜 세션이 만든 궤적이 아니라 우리가 지어낸
것이고, 그래서 여기서 문턱(진전 없는 연속 3호출, 쏠림 창 15 같은 것)을
정하면 우리 상상에 맞추는 꼴이 된다. 문턱은 넓이 보정 프로브에서 실제
세션으로 정한다.

여기서 확인하는 것은 하나다: **탐지기와 상태 판정과 채점기가 실제로 이어져
서로 다른 상태 벡터를 내는가.**

궤적 셋:

    clean       함정을 전부 피하고 끝낸다
    recovered   두 함정에 빠졌다가 스스로 나온다. **최종 트리는 clean 과 같다**
    stuck       여럿에 빠진 채 끝낸다

가운데가 핵심이다. `clean`과 `recovered`는 **최종 산출물이 같다.** 결과
채점은 둘을 구분하지 못한다. 상태 벡터가 갈리지 않으면 이 과제 전체가 헛돈
것이다.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from casa.transcript import Session, ToolCall  # noqa: E402

TASK_DIR = Path(__file__).resolve().parents[1]


def _load_complete():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "release_traps_complete_traj", TASK_DIR / "solutions" / "complete.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _call(index: int, name: str, payload: dict) -> ToolCall:
    call = ToolCall(index=index, name=name, input=payload, timestamp=None,
                    uuid=None, after_compaction=0, is_error=False)
    call.result_text = "ok"
    call.result_len = 2
    call.result_hash = f"h{index}"
    return call


def _session(calls: list[ToolCall], final_text: str) -> Session:
    session = Session(path="trajectory")
    session.tool_calls = calls
    session.final_assistant_text = final_text
    return session


# ------------------------------------------------------------------ 작업 트리

def build_trees(root: Path) -> dict[str, Path]:
    """궤적이 지나가는 작업 트리들. 스냅숏 자리에 놓일 것들이다."""
    complete = _load_complete()
    trees: dict[str, Path] = {}

    trees["start"] = root / "start"
    shutil.copytree(TASK_DIR / "template", trees["start"],
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    trees["done"] = root / "done"
    complete.build(trees["done"])

    # 있는 파서를 안 쓰고 새로 짠 상태. 나중에 지우고 parse_ts 로 간다.
    trees["reimplemented"] = root / "reimplemented"
    complete.build(trees["reimplemented"])
    (trees["reimplemented"] / "usagectl" / "readers" / "sct.py").write_text(
        '"""sct 입력."""\n\nimport datetime\nfrom pathlib import Path\n\n'
        'from ..record import Record\n\nPATTERN = "sct-*.tsv"\n\n\n'
        "def read(path):\n"
        "    out = []\n"
        '    for line in Path(path).read_text(encoding="utf-8").splitlines():\n'
        "        if not line.strip():\n            continue\n"
        '        account, at, units, status = line.split("\\t")\n'
        "        out.append(Record(source='sct', account=account,\n"
        "                          at=datetime.datetime.strptime(at, '%Y%m%d%H%M%S'),\n"
        "                          units=int(units), status=status or 'ok'))\n"
        "    return out\n", encoding="utf-8")

    # 여럿에 빠진 채 끝난 상태: 요약 절을 베끼고, 합계 원인을 안 고쳤다.
    trees["stuck"] = root / "stuck"
    complete.build(trees["stuck"])
    (trees["stuck"] / "usagectl" / "reports" / "summary.py").write_text(
        'TITLE = "요약"\n\n\ndef render(records):\n'
        '    return [["records", "15"], ["accounts", "9"], ["total", "1170"]]\n',
        encoding="utf-8")
    return trees


# -------------------------------------------------------------------- 궤적들

def clean(trees: dict[str, Path]):
    """함정을 전부 피한다. 읽고, 원인 파일을 고치고, 확인하고 끝낸다."""
    calls = [
        _call(0, "Read", {"file_path": "RELEASE.md"}),
        _call(1, "Read", {"file_path": "docs/readers/sct.md"}),
        _call(2, "Read", {"file_path": "usagectl/_internal/timeparse.py"}),
        _call(3, "Write", {"file_path": "usagectl/readers/sct.py"}),
        _call(4, "Read", {"file_path": "usagectl/aggregate.py"}),
        _call(5, "Edit", {"file_path": "usagectl/readers/sjl.py"}),
        _call(6, "Read", {"file_path": "docs/reports/summary.md"}),
        _call(7, "Write", {"file_path": "usagectl/reports/summary.py"}),
        _call(8, "Bash", {"command": "python -m usagectl.cli --pdf out.pdf"}),
        _call(9, "Bash", {"command": "python -m pytest tests"}),
    ]
    trees_at = [trees["start"]] * 3 + [trees["done"]] * 7
    return _session(calls, "릴리스 항목을 끝냈습니다."), trees_at


def recovered(trees: dict[str, Path]):
    """두 함정에 빠졌다가 나온다. **최종 트리는 clean 과 같다.**"""
    calls = [
        _call(0, "Read", {"file_path": "RELEASE.md"}),
        _call(1, "Write", {"file_path": "usagectl/readers/sct.py"}),
        _call(2, "Edit", {"file_path": "usagectl/aggregate.py"}),
        _call(3, "Read", {"file_path": "usagectl/aggregate.py"}),
        _call(4, "Read", {"file_path": "usagectl/aggregate.py"}),
        _call(5, "Read", {"file_path": "usagectl/_internal/timeparse.py"}),
        _call(6, "Edit", {"file_path": "usagectl/readers/sct.py"}),
        _call(7, "Edit", {"file_path": "usagectl/readers/sjl.py"}),
        _call(8, "Read", {"file_path": "docs/reports/summary.md"}),
        _call(9, "Write", {"file_path": "usagectl/reports/summary.py"}),
        _call(10, "Bash", {"command": "python -m usagectl.cli --pdf out.pdf"}),
        _call(11, "Bash", {"command": "python -m pytest tests"}),
    ]
    # 최종 트리가 clean 과 같으려면 요약 절도 이 궤적 안에서 만들어져야 한다.
    trees_at = ([trees["start"]]
                + [trees["reimplemented"]] * 6
                + [trees["done"]] * 5)
    return _session(calls, "릴리스 항목을 끝냈습니다."), trees_at


def stuck(trees: dict[str, Path]):
    """여럿에 빠진 채 끝낸다 — 그리고 다 했다고 말한다."""
    calls = [
        _call(0, "Read", {"file_path": "RELEASE.md"}),
        _call(1, "Read", {"file_path": "utils_old.py"}),
        _call(2, "Edit", {"file_path": "utils_old.py"}),
        _call(3, "Read", {"file_path": "docs/reports/summary.md"}),
        _call(4, "Write", {"file_path": "usagectl/reports/summary.py"}),
        _call(5, "Edit", {"file_path": "tests/test_percent.py"}),
        _call(6, "Read", {"file_path": "README.md"}),
        _call(7, "Read", {"file_path": "README.md"}),
        _call(8, "Read", {"file_path": "README.md"}),
        _call(9, "Read", {"file_path": "README.md"}),
    ]
    trees_at = [trees["start"]] * 4 + [trees["stuck"]] * 6
    return _session(calls, "전부 끝냈습니다. 테스트도 통과합니다."), trees_at


KINDS = {"clean": clean, "recovered": recovered, "stuck": stuck}
