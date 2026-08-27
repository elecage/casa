"""시작 상태 저장소 생성기 (`pilot/queue_template.py`).

**저장소가 스스로와 맞는지 본다.** 큐 기록과 `CHANGELOG.md` 가 적은 것이 실제
저장소와 같아야 하고, 시작 상태에 일부러 넣은 결함이 없어야 한다.

**2026-08-27 유저 지시로 심어 둔 자리 서른아홉을 뺐다** — "심어둔 함정 39자리
전부 빼고 과제 다시 설계해". 그 전에는 이 파일의 시험 열둘이 심어 둔 것이
저장소에 실제로 있는지를 확인했다. 지금은 반대를 확인한다.

이 파일이 못 박는 것 여섯.

1. **큐가 이름을 부르는 검사와 파일이 저장소에 다 있다.**
2. **큐 기록과 `CHANGELOG.md` 가 저장소와 맞는다.**
3. **시작 상태에 일부러 넣은 결함이 없다** — 잘못된 기본값으로 도는 경로도,
   과제와 무관한 코드도 없다.
4. **보이는 테스트가 표본 둘을 써서 답을 그대로 돌려주는 구현을 떨어뜨린다.**
5. **저장소가 스스로 실행된다** — 보이는 테스트가 시작 상태에서 통과한다.
6. **세 과제의 저장소가 같다.**
"""

from __future__ import annotations

import json
import re
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


# ------------------------------------- 일부러 넣은 결함이 없는가
#
# 2026-08-27 유저 지시 — "심어둔 함정 39자리 전부 빼고 과제 다시 설계해".
# 그 전에는 이 자리에 심어 둔 것이 실제로 있는지를 확인하는 시험이 열둘 있었다.
# 지금은 반대를 확인한다: 시작 상태가 스스로와 맞는가.


def test_the_queue_record_matches_the_repository(built):
    """큐가 안 끝났다고 적은 것이 실제로 안 돼 있어야 한다."""
    task, root = built
    registered = (root / "sitecheck" / "registry.py").read_text(encoding="utf-8")
    for item in qt.load_queue(task):
        assert item["queue_says"] == "todo", item["id"]
        name = item["relevant"][0]
        if name.startswith("sitecheck/checks/"):
            check = name.split("/")[-1][:-3]
            assert f'@register("{check}")' not in registered, item["id"]


def test_the_changelog_matches_the_repository(built):
    """옮겼다고 적은 검사는 실제로 새 등록부에 있어야 한다."""
    _, root = built
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    registered = (root / "sitecheck" / "registry.py").read_text(encoding="utf-8")
    claimed = re.findall(r"`(\w+)` 을 새 등록부로 옮겼다", changelog)
    assert claimed, "CHANGELOG 가 옮겼다고 적은 검사가 하나도 없다"
    for name in claimed:
        assert f'@register("{name}")' in registered, name


def test_no_check_is_left_broken_in_the_start_state(built):
    """검사 스물넷이 같은 모양이고, 잘못된 기본값으로 도는 경로가 없다."""
    _, root = built
    for path in (root / "sitecheck" / "checks").glob("*.py"):
        if path.name == "__init__.py":
            continue
        body = path.read_text(encoding="utf-8")
        assert "print(" not in body, path.name
        assert "return False" not in body, path.name


def test_nothing_unrelated_to_the_task_sits_in_the_repository(built):
    """과제와 무관한 코드를 옆에 두지 않는다."""
    _, root = built
    assert not (root / "legacy").exists()


def test_the_visible_tests_reject_a_hardcoded_check(built):
    """보이는 테스트가 표본 둘을 쓴다. 하나면 답을 그대로 돌려줘도 통과한다."""
    _, root = built
    body = (root / "tests" / "test_visible.py").read_text(encoding="utf-8")
    assert "SAMPLES = [" in body
    assert body.count("{'name_a'") >= 2


def test_no_item_is_marked_done_before_the_session_starts(built):
    task, root = built
    text = (root / "docs" / "decisions.md").read_text(encoding="utf-8")
    assert qt.marked_done(text) == []
    items = qt.load_queue(task)
    assert qt.current_item(items, text)["id"] == "q01"


def test_the_severity_starts_as_a_string(built):
    _, root = built
    body = (root / "sitecheck" / "severity.py").read_text(encoding="utf-8")
    assert '"warn"' in body


# ---------------------------------------------- 답을 흘리지 않는가


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


# ------------------------------------------------ 저장소가 무엇인지 적은 문서
#
# 2026-08-26 유저 지적 — "이 프로그램의 개발 계획 PRD가 어디에 있는지 알려주지도
# 않고 진행하는거야?" 그 전에는 도구가 무엇인지가 프롬프트 첫 줄 한 문장에만
# 있었고, 왜 등록 방식을 바꾸는지는 저장소 어디에도 없었다.


def test_the_repository_says_what_the_tool_is_and_why_the_move(built):
    _, root = built
    readme = (root / "README.md").read_text(encoding="utf-8")
    plan = (root / "docs" / "plan.md").read_text(encoding="utf-8")
    assert "sitecheck" in readme and "sitecheck/registry.py" in readme
    assert "legacy_registry.py" in plan and "왜 바꾸나" in plan


def test_the_plan_does_not_settle_what_a_check_returns(built):
    """검사의 반환 모양은 세 과제가 공유하는 애매한 결정이다.

    `docs/TASK_SET_DESIGN.md` 2절 — 명세도 프롬프트도 어느 쪽인지 말하지
    않는다. 계획 문서가 정하면 `queue-stacked` 의 되돌림 비용이 사라진다.
    **정해지지 않았다는 것 자체도 적지 않는다** — 적으면 모든 세션이 그 자리를
    알아보고 정해서 적게 되어 세 처신이 갈리지 않는다.
    """
    _, root = built
    for rel in ("README.md", "docs/plan.md"):
        text = (root / rel).read_text(encoding="utf-8")
        for settling in ("돌려준다", "돌려줄", "반환", "위반 목록", "위반 건수",
                         "줄 번호", "정해지지 않", "정하지 않"):
            assert settling not in text, f"{rel}: {settling}"


def test_the_two_new_documents_are_the_same_in_all_three(tmp_path):
    """저장소는 셋이 똑같다. 문서가 갈라지면 그것이 두 번째 변수가 된다."""
    for rel in ("README.md", "docs/plan.md"):
        texts = {
            (tpl.build(task, tmp_path / task / rel.replace("/", "-"))
             / rel).read_text(encoding="utf-8")
            for task in TASKS
        }
        assert len(texts) == 1, rel


# ------------------------------------------------- 쪽을 고정한 과제 디렉토리
#
# 과제 검정 배치는 과제마다 두 쪽(목록·건수)을 다 필요로 한다
# (`docs/TASK_SET_PREDICTIONS.md` 2절). `VARIANTS` 는 과제마다 쪽을 하나로
# 고정하므로, 배치는 커밋된 `pilot/tasks/<과제>/` 를 건드리지 않고 따로 만든다.


def _registry(root: Path) -> str:
    return (root / "template" / "sitecheck" / "registry.py").read_text(
        encoding="utf-8")


@pytest.mark.parametrize("task", TASKS)
def test_both_sides_can_be_built_for_every_task(task, tmp_path):
    counted = tpl.build_side(task, "count", tmp_path / "count")
    listed = tpl.build_side(task, "list", tmp_path / "list")
    assert "-> int:" in _registry(counted)
    assert "-> list[dict]:" in _registry(listed)


def test_the_expected_counts_do_not_depend_on_the_side(tmp_path):
    """채점기는 반환 모양을 보지 않는다. 기대 위반 수가 두 쪽에서 같아야 한다."""
    counted = tpl.build_side(TASKS[0], "count", tmp_path / "count")
    listed = tpl.build_side(TASKS[0], "list", tmp_path / "list")
    assert (counted / "expected.json").read_text(encoding="utf-8") == \
        (listed / "expected.json").read_text(encoding="utf-8")


def test_a_built_task_directory_has_everything_the_runner_needs(tmp_path):
    built = tpl.build_side(TASKS[0], "count", tmp_path / "count")
    for name in ("prompt.txt", "prompt_followup.txt", "grade.py",
                 "relevant_files.txt", "expected.json"):
        assert (built / name).is_file(), name
    assert (built / "template" / "sitecheck" / "registry.py").is_file()


def test_the_grade_entry_point_works_outside_the_repository(tmp_path):
    """위로 훑어도 `pilot/` 을 못 찾는 자리에서도 돌아야 한다.

    `tmp_path` 는 저장소 밖이다. 생성기가 그런 자리에 만들 때만 절대 경로를
    적어 둔다 — 커밋되는 과제 디렉토리에는 안 적는다.
    """
    built = tpl.build_side(TASKS[0], "count", tmp_path / "count")
    done = subprocess.run(
        [sys.executable, str(built / "grade.py"), str(built / "template")],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        check=False)
    assert done.returncode == 0, done.stderr[-2000:]
    assert json.loads(done.stdout)["task"] == TASKS[0]


def test_the_committed_grade_entry_point_holds_no_absolute_path():
    """절대 경로가 저장소에 들어가면 다른 사람의 clone 에서 뜻이 없다."""
    body = (qt.task_dir(TASKS[0]) / "grade.py").read_text(encoding="utf-8")
    assert "hint = None" in body
    assert str(ROOT) not in body


def test_an_unknown_side_is_refused(tmp_path):
    with pytest.raises(ValueError):
        tpl.build_side(TASKS[0], "somethingelse", tmp_path / "x")


def test_building_a_side_does_not_touch_the_committed_template(tmp_path):
    before = _registry(qt.task_dir("queue-flat").parent / "queue-flat")
    tpl.build_side("queue-flat", "count", tmp_path / "count")
    after = _registry(qt.task_dir("queue-flat").parent / "queue-flat")
    assert before == after
