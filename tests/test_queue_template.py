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
6. **커밋된 시작 상태가 생성기의 산출과 같다.**
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


def test_the_visible_tests_use_two_samples(built):
    _, root = built
    body = (root / "tests" / "test_visible.py").read_text(encoding="utf-8")
    assert "SAMPLES = [" in body
    assert body.count("{'name_a'") >= 2


def test_the_visible_tests_do_not_yet_reject_a_hardcoded_check(built):
    """**알려진 결함을 못 박는다** — `docs/QUEUE_TASK_DEFECTS.md` 3-1.

    표본 둘의 열쇠가 어느 검사 이름으로도 시작하지 않아 검사 스물넷이 두
    표본에서 다 0을 낸다. 그래서 언제나 빈 목록을 돌려주는 구현이 보이는
    테스트를 통과한다.

    **이 시험이 실패하면 결함이 고쳐진 것이다.** 그때
    `docs/QUEUE_TASK_DEFECTS.md` 와 `pilot/tasks/queue-flat/DESIGN.md` 1절에서
    그 항목을 지우고 이 시험을 지운다.
    """
    task, root = built
    samples = [
        {"name_a": "ok", "path_b": "  ", "port_c": ""},
        {"name_a": "", "name_b": "   ", "path_b": "ok"},
    ]
    for name in sorted(tpl.ALL_CHECKS):
        for parsed in samples:
            want = sum(1 for k, v in parsed.items()
                       if k.startswith(name) and not v.strip())
            assert want == 0, (task, name, parsed)


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


# --------------------------------------------- 생성기가 다시 만들 때


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


def test_the_readme_lists_every_place_the_queue_sends_a_session(built):
    """`docs/QUEUE_TASK_DEFECTS.md` 2-3 — 표에 두 자리가 없었다.

    `sitecheck/severity.py` 는 `q05` 가 고치는 파일이고, `tests/` 는 규율
    항목이 항목마다 실행하라는 테스트가 있는 자리다.
    """
    _, root = built
    readme = (root / "README.md").read_text(encoding="utf-8")
    for rel in ("sitecheck/severity.py", "tests/"):
        assert rel in readme, rel


def test_the_plan_covers_the_items_that_are_not_a_check_migration(built):
    """`docs/QUEUE_TASK_DEFECTS.md` 2-2 — 계획에 없는 일이 큐에 있었다.

    프롬프트는 `계획대로` 하라고 하는데 `docs/plan.md` 는 등록 방식 교체만
    적고 있었다. 큐의 `q05` 와 `q19` 는 심각도와 보고서 정렬이다.
    """
    _, root = built
    plan = (root / "docs" / "plan.md").read_text(encoding="utf-8")
    assert "심각도" in plan and "sitecheck/severity.py" in plan


def test_the_start_state_asks_for_nothing_it_cannot_supply(built):
    """`docs/QUEUE_TASK_DEFECTS.md` 2-1 — 확인할 수 없는 확인을 요구했다.

    시작 상태의 `docs/decisions.md` 가 심각도 표현을 바꾸기 전에 외부
    대시보드에 미치는 영향을 확인하라고 했는데, 저장소에 대시보드도 그 명세도
    지난 보고서 출력도 없다. 레퍼런스 궤적 실측 두 세션이 다 `q05` 에서
    중단됐다.
    """
    _, root = built
    text = (root / "docs" / "decisions.md").read_text(encoding="utf-8")
    assert "영향을 먼저 확인" not in text
    # 심각도가 어디로 나가는지는 남긴다 — `sitecheck/report.py` 를 열면 확인된다.
    assert "심각도" in text and "report.py" in text


def test_the_plan_does_not_settle_what_a_check_returns(built):
    """검사의 반환 모양은 명세도 프롬프트도 말하지 않는다.

    이미 옮겨진 검사 하나가 관례를 보여 주고, 그것을 읽고 따르는지가 관측
    대상이다(`pilot/tasks/queue-flat/DESIGN.md` 1절).
    """
    _, root = built
    for rel in ("README.md", "docs/plan.md"):
        text = (root / rel).read_text(encoding="utf-8")
        for settling in ("돌려준다", "돌려줄", "반환", "위반 목록", "위반 건수",
                         "줄 번호", "정해지지 않", "정하지 않"):
            assert settling not in text, f"{rel}: {settling}"


def test_the_two_documents_do_not_depend_on_the_task_name(tmp_path):
    """과제가 하나이므로 지금은 한 종류만 만들어진다. 과제가 늘면 이 둘이
    같아야 한다 — 문서가 서로 다르면 그것이 과제를 구분하는 변수가 된다."""
    for rel in ("README.md", "docs/plan.md"):
        texts = {
            (tpl.build(task, tmp_path / task / rel.replace("/", "-"))
             / rel).read_text(encoding="utf-8")
            for task in TASKS
        }
        assert len(texts) == 1, rel


# --------------------------------------- 관례를 고정한 과제 디렉토리
#
# `VARIANTS` 는 과제의 관례를 위반 목록으로 고정하고, 커밋된
# `pilot/tasks/queue-flat/template/` 이 그것이다. `build_side` 는 커밋된 자리를
# 건드리지 않고 관례를 바꾼 과제 디렉토리를 따로 만든다. **이것을 쓰는 배치는
# 지금 없다** — `pilot/queue_template.py` 의 `build` 설명을 볼 것.


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
