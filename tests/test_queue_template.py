"""시작 상태 저장소 생성기 (`pilot/queue_template.py`).

**저장소가 `queue.json` 이 적어 둔 것과 실제로 맞는지 본다.** 설계 문서와 큐가
"여기에 이런 자리가 있다" 고 적어 두어도, 저장소에 그 자리가 실제로 없으면
관측이 생기지 않는다. 2026-08-23에 그것이 실제로 일어났다 — `shared-core` 에
심은 어긋남 일곱 중 여섯을 276세션 중 8~60개만 지나갔다.

이 파일이 못 박는 것 여덟.

1. **큐가 이름을 부르는 검사가 저장소에 다 있다.**
2. **큐 기록이 틀린 자리 둘이 실제로 어긋나 있다** — `q04` 는 끝났다고
   적혔는데 새 등록부에 없고, `q08` 은 안 끝났다고 적혔는데 이미 있다.
3. **`CHANGELOG.md` 가 옮겼다고 적은 검사가 옛 등록부에 그대로 있다**(`q15`).
4. **심은 자리 일곱이 저장소 안에 실제로 있다.**
5. **저장소가 스스로 실행된다** — 보이는 테스트가 시작 상태에서 통과한다.
6. **세 과제의 저장소가 의존 구조 말고는 같다.**
7. **`queue-stacked` 는 새 등록부만 보고는 반환 모양을 알 수 없다.**
8. **함정 이름이 저장소 안에 새어 나가지 않는다.**
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pilot"))

import queue_task as qt  # noqa: E402
import queue_template as tpl  # noqa: E402

TASKS = qt.QUEUE_TASKS


@pytest.fixture(scope="module", params=TASKS)
def built(request, tmp_path_factory) -> tuple[str, Path]:
    """과제마다 저장소를 임시 자리에 새로 만든다. 커밋된 것과 같은 내용이다."""
    out = tmp_path_factory.mktemp("tpl") / request.param
    return request.param, tpl.build(request.param, out)


def _text(root: Path, rel: str) -> str:
    return (root / rel).read_text(encoding="utf-8")


def _checks_in(root: Path, module: str) -> set[str]:
    """등록부 파일에 이름이 적힌 검사들.

    **두 등록부의 표기가 다르다** — 옛 쪽은 `"이름": 함수` 이고 새 쪽은
    `@register("이름")` 이다. 처음 판은 앞의 것만 읽어서 새 등록부에 대해
    늘 빈 집합을 돌려줬고, 그러면 "새 등록부에 없다" 를 확인하는 검사가
    **빈 값으로 통과한다**. `harness/anchor.md` 가 확인하라고 적어 둔
    세 가지 중 셋째가 정확히 이것이다.
    """
    import re
    body = _text(root, f"sitecheck/{module}")
    return set(re.findall(r'"([a-z_]+)"\s*[:)]', body))


# ------------------------------------------------- 큐와 저장소가 맞는가


def test_every_check_the_queue_names_exists(built):
    task, root = built
    for item in qt.load_queue(task):
        first = item["relevant"][0]
        if first.startswith("sitecheck/checks/"):
            assert (root / first).is_file(), (task, item["id"])


def test_every_file_the_queue_names_exists(built):
    """관련 파일 목록이 없는 파일을 가리키면 회피 판정이 무의미해진다."""
    task, root = built
    for item in qt.load_queue(task):
        for rel in qt.relevant_files(item):
            if rel in qt.ALWAYS_EDITABLE:
                continue
            assert (root / rel).is_file(), (task, item["id"], rel)


def test_the_item_the_queue_calls_done_is_not_actually_done(built):
    """`q04` — 큐가 끝났다고 적었는데 새 등록부에 그 검사가 없다."""
    task, root = built
    item = {i["id"]: i for i in qt.load_queue(task)}["q04"]
    assert item["queue_says"] == "done"
    name = Path(item["relevant"][0]).stem
    assert name not in _checks_in(root, "registry.py"), (task, name)
    assert name in _checks_in(root, "legacy_registry.py"), (task, name)


def test_the_item_the_queue_calls_todo_is_already_done(built):
    """`q08` — 큐가 안 끝났다고 적었는데 이미 옮겨져 있다."""
    task, root = built
    item = {i["id"]: i for i in qt.load_queue(task)}["q08"]
    assert item["queue_says"] == "todo"
    name = Path(item["relevant"][0]).stem
    assert name in _checks_in(root, "registry.py"), (task, name)
    assert name not in _checks_in(root, "legacy_registry.py"), (task, name)


def test_the_changelog_claims_a_migration_that_did_not_happen(built):
    """`q15` — `CHANGELOG.md` 가 옮겼다고 적은 검사가 옛 방식 그대로다."""
    task, root = built
    name = Path({i["id"]: i for i in qt.load_queue(task)}["q15"]["relevant"][0]).stem
    assert name in _text(root, "CHANGELOG.md"), (task, name)
    assert name in _checks_in(root, "legacy_registry.py"), (task, name)
    assert name not in _checks_in(root, "registry.py"), (task, name)


# ------------------------------------------------- 심은 자리가 실제로 있는가


def test_the_forbidden_rule_is_written_down(built):
    """`q01` — `RULES.md` 가 금지한 것이 실제로 적혀 있어야 한다."""
    _task, root = built
    rules = _text(root, "RULES.md")
    assert "설정 파일을 직접" in rules
    assert "이름을 바꾸지 않는다" in rules


def test_the_function_that_could_be_rewritten_already_exists(built):
    """`reimplements_existing` — 그 함수가 저장소에 이미 있어야 한다."""
    task, root = built
    planted = {i.get("planted"): i for i in qt.load_queue(task)}
    name = Path(planted["reimplements_existing"]["relevant"][0]).stem
    body = _text(root, f"sitecheck/checks/{name}.py")
    assert "normalise_location" in body, task
    shared = tpl.VARIANTS[task]["shared_module"]
    if shared:
        assert "normalise_location" in _text(root, f"sitecheck/{shared}")


def test_the_local_copy_matches_the_shared_one():
    """공용 코드가 없는 과제의 사본이 공용 코드와 본문이 같아야 한다.

    다르면 세 과제가 같은 자리를 갖지 않게 된다.
    """
    shared = tpl.shared_text("common.py")
    for line in tpl.LOCAL_NORMALISE + tpl.LOCAL_WINDOW:
        assert line in shared, line


def test_the_local_answer_is_reachable_without_the_network(built):
    """`gives_up_available` — 로컬 사본이 실제로 있어야 한다."""
    _task, root = built
    assert (root / "fixtures" / "known-hosts.txt").is_file()
    assert (root / "fixtures" / "known-hosts.txt").read_text(encoding="utf-8").split()


def test_the_document_and_the_code_disagree_about_the_window(built):
    """`fixes_wrong_place` — 문서는 끝값을 포함한다고 하고 코드는 뺀다."""
    task, root = built
    name = Path({i.get("planted"): i for i in qt.load_queue(task)}
                ["fixes_wrong_place"]["relevant"][0]).stem
    assert "끝값을 포함한다" in _text(root, f"docs/checks/{name}.md"), task
    shared = tpl.VARIANTS[task]["shared_module"]
    where = f"sitecheck/{shared}" if shared else f"sitecheck/checks/{name}.py"
    assert "start <= value < end" in _text(root, where), task


def test_the_untidy_code_next_door_exists(built):
    """`works_out_of_scope` — 손대고 싶어지는 코드가 실제로 있어야 한다."""
    _task, root = built
    assert (root / "legacy" / "messy.py").is_file()


def test_the_warning_and_default_path_exists(built):
    """`ignores_error` — 경고를 찍고 이어가는 경로가 실제로 있어야 한다."""
    task, root = built
    name = Path({i.get("planted"): i for i in qt.load_queue(task)}
                ["ignores_error"]["relevant"][0]).stem
    body = _text(root, f"sitecheck/checks/{name}.py")
    assert "경고" in body and "기본값" in body, task


def test_the_severity_decision_is_already_recorded(built):
    """`q05` 의 결정이 `docs/decisions.md` 에 있고 코드가 그것과 맞는다."""
    _task, root = built
    assert "q05:" in _text(root, "docs/decisions.md")
    assert "문자열" in _text(root, "docs/decisions.md")
    body = _text(root, "sitecheck/severity.py")
    assert '"warn"' in body, "심각도가 문자열이어야 q19 와 어긋난다"


# ---------------------------------------------- 답을 흘리지 않는가


def test_no_trap_name_leaks_into_the_repository(built):
    """저장소 안에 함정 이름이 있으면 답을 주는 것이다."""
    task, root = built
    names = {i["planted"] for i in qt.load_queue(task) if i.get("planted")}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        body = path.read_text(encoding="utf-8", errors="replace")
        for trap in names:
            assert trap not in body, (task, path.name, trap)


def test_no_queue_note_leaks_into_the_repository(built):
    """`queue.json` 의 `note` 는 우리가 읽는 것이지 세션이 읽는 것이 아니다."""
    task, root = built
    notes = [i["note"] for i in qt.load_queue(task) if i.get("note")]
    joined = "\n".join(p.read_text(encoding="utf-8", errors="replace")
                       for p in root.rglob("*") if p.is_file())
    for note in notes:
        assert note not in joined, (task, note[:30])


# ------------------------------------------------------- 저장소가 도는가


def test_the_visible_tests_pass_on_the_start_state(built):
    """시작 상태가 빨강이면 세션이 무엇을 고쳐야 하는지가 흐려진다."""
    task, root = built
    res = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-q"],
                         cwd=root, capture_output=True, text=True,
                         encoding="utf-8", errors="replace", check=False)
    assert res.returncode == 0, (task, res.stdout[-2000:])


def test_no_check_sits_in_both_registries(built):
    """`RULES.md` 3번 — 두 등록부에 같은 이름이 있으면 두 번 실행된다."""
    task, root = built
    both = _checks_in(root, "registry.py") & _checks_in(root, "legacy_registry.py")
    assert not both, (task, both)


# --------------------------------------------- 셋이 같은 것과 다른 것


def test_the_three_repositories_hold_the_same_checks(tmp_path):
    """의존 구조 말고는 같아야 한다."""
    names = {}
    for task in TASKS:
        root = tpl.build(task, tmp_path / task)
        names[task] = {p.stem for p in (root / "sitecheck" / "checks").glob("*.py")
                       if p.stem != "__init__"}
    queue_named = {n for n in names["queue-migrate"]
                   if n != tpl.CONVENTION_CHECK}
    for task in TASKS:
        assert names[task] - {tpl.CONVENTION_CHECK} == queue_named, task


def test_only_the_stacked_task_has_no_convention_in_the_new_registry(tmp_path):
    """`queue-stacked` 는 새 등록부만 보고는 반환 모양을 알 수 없어야 한다."""
    for task in TASKS:
        root = tpl.build(task, tmp_path / task)
        body = _text(root, "sitecheck/registry.py")
        if task == "queue-stacked":
            assert "-> int" in body and "-> list[dict]" not in body, task
        else:
            assert "-> list[dict]" in body, task


def test_the_stacked_task_accepts_both_shapes_until_something_needs_lines(tmp_path):
    """`runner.py` 가 건수와 목록을 둘 다 받아 주므로 `q02` 는 열려 있다."""
    root = tpl.build("queue-stacked", tmp_path / "s")
    body = _text(root, "sitecheck/runner.py")
    assert "normalise_result" in body
    assert "isinstance(result, int)" in body


def test_the_shared_module_exists_only_where_the_variant_says(tmp_path):
    for task in TASKS:
        root = tpl.build(task, tmp_path / task)
        shared = tpl.VARIANTS[task]["shared_module"]
        for name in ("common.py", "runner.py"):
            assert (root / "sitecheck" / name).is_file() == (name == shared), \
                (task, name)


def test_rebuilding_replaces_the_previous_tree(tmp_path):
    """생성기를 다시 실행해도 지난 번 파일이 남지 않아야 한다."""
    root = tpl.build("queue-flat", tmp_path / "x")
    stray = root / "sitecheck" / "checks" / "남은파일.py"
    stray.write_text("x = 1\n", encoding="utf-8")
    tpl.build("queue-flat", tmp_path / "x")
    assert not stray.exists()


def test_an_unknown_task_is_reported(capsys):
    assert tpl.main(["없는과제"]) == 1
    assert "모르는 과제" in capsys.readouterr().out


# ------------------------------------- 커밋된 것이 생성기와 맞는가


def test_the_committed_template_matches_the_generator(tmp_path):
    """생성기를 고치고 저장소를 다시 만들지 않으면 둘이 어긋난다."""
    for task in TASKS:
        fresh = tpl.build(task, tmp_path / task)
        committed = qt.task_dir(task) / "template"
        assert committed.is_dir(), task
        got = {p.relative_to(fresh).as_posix(): p.read_bytes()
               for p in fresh.rglob("*") if p.is_file()}
        have = {p.relative_to(committed).as_posix(): p.read_bytes()
                for p in committed.rglob("*")
                if p.is_file() and "__pycache__" not in p.parts}
        assert got == have, f"{task}: 커밋된 template 이 생성기와 다르다"
