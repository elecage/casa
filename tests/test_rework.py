"""`pilot/analysis/rework.py` — 되돌리는 비용 산출.

순수 계산(줄 세기·경계 나누기)은 따로 판정하고, git 을 실제로 쓰는 부분은
작은 스냅숏 저장소를 만들어 확인한다.
"""

import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent

spec = importlib.util.spec_from_file_location(
    "rework", REPO / "pilot" / "analysis" / "rework.py")
rework = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rework)


def _git_env() -> dict:
    """호출한 쪽의 git 환경을 물려주지 않는다.

    우리 pre-commit 훅이 테스트를 실행하므로 `GIT_INDEX_FILE` 이 들어온다.
    그대로 두면 이 테스트가 만드는 커밋이 **이 저장소의 색인**에 담긴다.
    """
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update({"GIT_AUTHOR_NAME": "casa", "GIT_AUTHOR_EMAIL": "casa@local",
                "GIT_COMMITTER_NAME": "casa", "GIT_COMMITTER_EMAIL": "casa@local"})
    return env


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True,
                          env=_git_env())


# ------------------------------------------------------------ 줄 세기

def test_short_lines_are_not_counted():
    """공백 줄과 닫는 괄호는 어느 파일에나 있어 남았는지가 뜻이 없다."""
    assert rework.significant("def compute(value):")
    assert not rework.significant("")
    assert not rework.significant("   ")
    assert not rework.significant("}")
    assert not rework.significant("  )")


def test_excluded_paths_cover_the_session_made_virtualenv():
    """스냅숏에 `.venv/` 가 통째로 들어가 있다. 안 빼면 실제 작업이 묻힌다."""
    assert rework.excluded(".venv/lib/python3.11/site-packages/pip/x.py")
    assert rework.excluded("node_modules/left-pad/index.js")
    assert not rework.excluded("core/money.py")
    assert not rework.excluded("docs/venv-notes.md")


def test_gone_counts_lines_missing_from_the_final_tree():
    from collections import Counter
    added = Counter({"return total": 2, "raise ValueError(msg)": 1})
    final = Counter({"return total": 1})
    # "return total" 둘 중 하나만 남았고, raise 줄은 사라졌다.
    assert rework.gone(added, final) == 2


def test_gone_is_zero_when_everything_survives():
    from collections import Counter
    added = Counter({"x = 1": 1})
    assert rework.gone(added, Counter({"x = 1": 3})) == 0


# --------------------------------------------------------- 세션 경계

def test_the_boundary_sits_between_two_sessions():
    """러너가 세션이 끝난 **뒤에** 스냅숏을 한 번 더 찍는다.

    트랜스크립트 끝 시각을 그대로 경계로 쓰면 그 마지막 스냅숏이 다음 세션
    몫으로 넘어간다.
    """
    windows = [(100.0, 200.0), (300.0, 400.0)]
    assert rework.boundaries(windows) == [250.0, float("inf")]


def test_a_single_session_has_no_upper_boundary():
    assert rework.boundaries([(10.0, 20.0)]) == [float("inf")]


def test_session_trees_split_commits_at_the_boundaries():
    rows = [("base", 90), ("a", 120), ("b", 180), ("c", 350)]
    trees = rework.session_trees(rows, [250.0, float("inf")])
    assert trees == [("base", "b"), ("b", "c")]


def test_a_session_that_changed_nothing_gets_no_pair():
    """세션이 파일을 하나도 안 바꾸면 스냅숏 커밋이 안 생긴다."""
    rows = [("base", 90), ("a", 120)]
    trees = rework.session_trees(rows, [250.0, float("inf")])
    assert trees == [("base", "a"), None]


def test_session_trees_survive_an_empty_repository():
    assert rework.session_trees([], [1.0, 2.0]) == [None, None]


# ------------------------------------------------- 실제 저장소로 확인

@pytest.fixture()
def snapshot_repo(tmp_path):
    """세션 둘짜리 스냅숏 저장소. 세션 2가 세션 1의 줄을 지운다."""
    work = tmp_path / "work"
    work.mkdir()
    git_dir = tmp_path / "chain-01.git"
    _run("git", "init", "-q", "--bare", str(git_dir), cwd=tmp_path)
    _run("git", f"--git-dir={git_dir}", "config", "core.bare", "false",
         cwd=tmp_path)

    def commit(message: str) -> str:
        _run("git", f"--git-dir={git_dir}", f"--work-tree={work}", "add", "-A",
             cwd=work)
        _run("git", f"--git-dir={git_dir}", f"--work-tree={work}", "commit",
             "-q", "--allow-empty", "-m", message, cwd=work)
        done = subprocess.run(
            ["git", f"--git-dir={git_dir}", "rev-parse", "HEAD"],
            cwd=work, capture_output=True, text=True, check=True,
            env=_git_env())
        return done.stdout.strip()

    (work / "core.py").write_text("KEEP_ME = 1\n", encoding="utf-8")
    base = commit("baseline")

    # 세션 1: 뜻 있는 줄 넷을 더한다.
    (work / "core.py").write_text(
        "KEEP_ME = 1\nSURVIVES = 2\nDELETED_LATER = 3\nALSO_DELETED = 4\n",
        encoding="utf-8")
    first = commit("call 1")

    # 세션 2: 세션 1이 더한 줄 둘을 지우고 자기 줄 하나를 더한다.
    (work / "core.py").write_text(
        "KEEP_ME = 1\nSURVIVES = 2\nADDED_BY_SESSION_TWO = 9\n",
        encoding="utf-8")
    second = commit("call 2")
    return {"git_dir": git_dir, "work": work,
            "base": base, "first": first, "second": second}


def test_added_lines_reads_what_the_session_wrote(snapshot_repo):
    counted = rework.added_lines(snapshot_repo["git_dir"],
                                 snapshot_repo["base"], snapshot_repo["first"])
    assert counted["SURVIVES = 2"] == 1
    assert counted["DELETED_LATER = 3"] == 1
    assert sum(counted.values()) == 3


def test_tree_lines_reads_the_final_state(snapshot_repo):
    final = rework.tree_lines(snapshot_repo["git_dir"], snapshot_repo["second"])
    assert final["ADDED_BY_SESSION_TWO = 9"] == 1
    assert final["DELETED_LATER = 3"] == 0


def test_the_later_session_undoing_work_is_counted(snapshot_repo):
    """세션 1이 더한 줄 셋 중 둘을 세션 2가 지웠다 — 되돌림 비율 2/3."""
    added = rework.added_lines(snapshot_repo["git_dir"],
                               snapshot_repo["base"], snapshot_repo["first"])
    final = rework.tree_lines(snapshot_repo["git_dir"], snapshot_repo["second"])
    missing = rework.gone(added, final)
    assert missing == 2
    assert missing / sum(added.values()) == pytest.approx(2 / 3)


def test_a_line_that_moved_to_another_file_still_counts_as_surviving(tmp_path):
    """뒤 세션이 파일을 옮기면 그 줄이 사라졌다고 세면 안 된다.

    그래서 남았는지를 그 파일 안이 아니라 **트리 전체**에서 찾는다.
    """
    work = tmp_path / "work"
    work.mkdir()
    git_dir = tmp_path / "c.git"
    _run("git", "init", "-q", "--bare", str(git_dir), cwd=tmp_path)
    _run("git", f"--git-dir={git_dir}", "config", "core.bare", "false",
         cwd=tmp_path)

    def commit(message):
        _run("git", f"--git-dir={git_dir}", f"--work-tree={work}", "add", "-A",
             cwd=work)
        _run("git", f"--git-dir={git_dir}", f"--work-tree={work}", "commit",
             "-q", "--allow-empty", "-m", message, cwd=work)
        return subprocess.run(
            ["git", f"--git-dir={git_dir}", "rev-parse", "HEAD"], cwd=work,
            capture_output=True, text=True, check=True,
            env=_git_env()).stdout.strip()

    (work / "a.py").write_text("PLACEHOLDER = 0\n", encoding="utf-8")
    base = commit("baseline")
    (work / "a.py").write_text("PLACEHOLDER = 0\nMOVED_LINE = 42\n",
                               encoding="utf-8")
    first = commit("call 1")
    (work / "a.py").write_text("PLACEHOLDER = 0\n", encoding="utf-8")
    (work / "b.py").write_text("MOVED_LINE = 42\n", encoding="utf-8")
    second = commit("call 2")

    added = rework.added_lines(git_dir, base, first)
    final = rework.tree_lines(git_dir, second)
    assert rework.gone(added, final) == 0


def test_the_virtualenv_is_left_out_of_the_counts(tmp_path):
    """세션이 만든 가상 환경이 스냅숏에 들어가 있어도 세지 않는다."""
    work = tmp_path / "work"
    (work / ".venv" / "lib").mkdir(parents=True)
    git_dir = tmp_path / "c.git"
    _run("git", "init", "-q", "--bare", str(git_dir), cwd=tmp_path)
    _run("git", f"--git-dir={git_dir}", "config", "core.bare", "false",
         cwd=tmp_path)

    def commit(message):
        _run("git", f"--git-dir={git_dir}", f"--work-tree={work}", "add", "-A",
             cwd=work)
        _run("git", f"--git-dir={git_dir}", f"--work-tree={work}", "commit",
             "-q", "--allow-empty", "-m", message, cwd=work)
        return subprocess.run(
            ["git", f"--git-dir={git_dir}", "rev-parse", "HEAD"], cwd=work,
            capture_output=True, text=True, check=True,
            env=_git_env()).stdout.strip()

    (work / "core.py").write_text("START = 1\n", encoding="utf-8")
    base = commit("baseline")
    (work / "core.py").write_text("START = 1\nREAL_WORK = 2\n", encoding="utf-8")
    (work / ".venv" / "lib" / "vendored.py").write_text(
        "\n".join(f"VENDORED_{i} = {i}" for i in range(500)), encoding="utf-8")
    first = commit("call 1")

    counted = rework.added_lines(git_dir, base, first)
    assert sum(counted.values()) == 1, "가상 환경 줄이 셈에 들어갔다"
    assert counted["REAL_WORK = 2"] == 1
    assert "VENDORED_3 = 3" not in rework.tree_lines(git_dir, first)


def test_binary_files_are_skipped(tmp_path):
    """세션이 PDF 를 만든다. 이진 파일을 줄로 세면 안 된다."""
    work = tmp_path / "work"
    work.mkdir()
    git_dir = tmp_path / "c.git"
    _run("git", "init", "-q", "--bare", str(git_dir), cwd=tmp_path)
    _run("git", f"--git-dir={git_dir}", "config", "core.bare", "false",
         cwd=tmp_path)
    (work / "report.pdf").write_bytes(b"%PDF-1.4\x00\x00binary\x00stuff\n")
    (work / "note.md").write_text("readable line here\n", encoding="utf-8")
    _run("git", f"--git-dir={git_dir}", f"--work-tree={work}", "add", "-A",
         cwd=work)
    _run("git", f"--git-dir={git_dir}", f"--work-tree={work}", "commit", "-q",
         "-m", "baseline", cwd=work)

    lines = rework.tree_lines(git_dir, "HEAD")
    assert lines["readable line here"] == 1
    assert not any("binary" in text for text in lines)


def test_the_handoff_document_is_left_out_of_the_main_count(tmp_path):
    """과제가 세션마다 `HANDOFF.md` 를 갱신하라고 지시한다.

    뒤 세션이 그것을 다시 쓰는 것은 되돌림이 아니다. 이 구분을 안 하면 인계
    문서를 길게 쓴 세션이 되돌림이 큰 세션으로 잡힌다.
    """
    work = tmp_path / "work"
    work.mkdir()
    git_dir = tmp_path / "c.git"
    _run("git", "init", "-q", "--bare", str(git_dir), cwd=tmp_path)
    _run("git", f"--git-dir={git_dir}", "config", "core.bare", "false",
         cwd=tmp_path)

    def commit(message):
        _run("git", f"--git-dir={git_dir}", f"--work-tree={work}", "add", "-A",
             cwd=work)
        _run("git", f"--git-dir={git_dir}", f"--work-tree={work}", "commit",
             "-q", "--allow-empty", "-m", message, cwd=work)
        return subprocess.run(
            ["git", f"--git-dir={git_dir}", "rev-parse", "HEAD"], cwd=work,
            capture_output=True, text=True, check=True,
            env=_git_env()).stdout.strip()

    (work / "HANDOFF.md").write_text("nothing done yet\n", encoding="utf-8")
    (work / "core.py").write_text("START = 1\n", encoding="utf-8")
    base = commit("baseline")
    (work / "HANDOFF.md").write_text(
        "did the rating module\nnext up is invoicing\n", encoding="utf-8")
    (work / "core.py").write_text("START = 1\nREAL_WORK = 2\n", encoding="utf-8")
    first = commit("call 1")

    main = rework.added_lines(git_dir, base, first)
    assert sum(main.values()) == 1, "인계 문서가 본 셈에 들어갔다"
    assert main["REAL_WORK = 2"] == 1

    handoff = rework.added_lines(git_dir, base, first,
                                 only=rework.REWRITTEN_BY_DESIGN)
    assert sum(handoff.values()) == 2
    assert handoff["next up is invoicing"] == 1


# --------------------------------------------------- 노출 기간 맞추기

def test_call_numbers_are_read_from_the_snapshot_subjects(snapshot_repo):
    rows = rework.numbered_commits(snapshot_repo["git_dir"])
    assert [number for _, _, number in rows] == [None, 1, 2]


def test_the_horizon_stops_at_the_requested_call_count():
    rows = [("base", 10, None), ("a", 20, 5), ("b", 30, 40),
            ("c", 40, 105), ("d", 50, 130)]
    # "a" 에서 100호출 뒤는 105 까지 — "c" 가 마지막으로 들어온다.
    assert rework.horizon_commit(rows, "a", 100) == "c"


def test_a_session_without_enough_room_left_is_not_scored():
    """사슬의 마지막 세션은 뒤에 아무도 없어 되돌림이 구조적으로 0이 된다.

    그 0을 다른 세션의 비율과 나란히 놓으면 위치가 신호로 새어 들어간다.
    """
    rows = [("base", 10, None), ("a", 20, 5), ("b", 30, 40)]
    assert rework.horizon_commit(rows, "b", 100) is None


def test_the_horizon_is_measured_from_the_session_end_not_the_chain_start():
    rows = [("base", 1, None), ("a", 2, 200), ("b", 3, 250), ("c", 4, 400)]
    # "a" 는 200 에서 끝났으므로 300 까지 본다 — "b"(250) 만 들어온다.
    assert rework.horizon_commit(rows, "a", 100) == "b"


def test_a_window_in_which_nothing_changed_points_back_at_the_session():
    """스냅숏은 파일이 바뀐 호출에만 생긴다.

    창 안에 커밋이 하나도 없다는 것은 그동안 아무도 그 세션의 것을 안 건드린
    것이므로, 그 세션의 끝 트리를 그대로 견주면 된다 — 되돌림 0이다.
    """
    rows = [("base", 1, None), ("a", 2, 200), ("b", 3, 250), ("c", 4, 400)]
    # "b" 는 250 에서 끝나 350 까지 보는데 그 사이에 커밋이 없다.
    assert rework.horizon_commit(rows, "b", 100) == "b"


def test_an_unknown_commit_gets_no_horizon():
    rows = [("base", 1, None), ("a", 2, 10)]
    assert rework.horizon_commit(rows, "missing", 100) is None


# ------------------------------------------------------------- 모아 적기

def _row(**kwargs) -> dict:
    row = {"cut": False, "flagged": False, "added_lines": 10, "gone_lines": 1,
           "rework_ratio": 0.1, "rework_ratio_h": 0.1}
    row.update(kwargs)
    return row


def test_cut_sessions_are_left_out_of_the_summary():
    """열 호출에서 멈춘 세션은 더한 줄이 거의 없어 비율이 뜻을 갖지 않는다."""
    rows = [
        _row(cut=True, flagged=True, rework_ratio_h=1.0, added_lines=1),
        _row(flagged=True, rework_ratio_h=0.5),
        _row(flagged=False, rework_ratio_h=0.1),
    ]
    summary = rework.summarize(rows)
    assert summary["n_sessions"] == 3
    assert summary["n_scored"] == 2
    assert summary["by_signal"]["flagged"]["n"] == 1
    assert summary["by_signal"]["unflagged"]["median"] == 0.1


def test_the_summary_uses_the_equalized_measure_by_default():
    """기본값은 노출 기간을 맞춘 값이어야 한다. 사슬 끝까지 본 값은 편향된다."""
    rows = [_row(rework_ratio=0.9, rework_ratio_h=0.2)]
    assert rework.summarize(rows)["all"]["median"] == 0.2
    assert rework.summarize(rows, "rework_ratio")["all"]["median"] == 0.9
    assert rework.summarize(rows)["measure"] == "rework_ratio_h"


def test_a_group_with_no_sessions_is_reported_as_such_not_as_zero():
    """관측이 없는 것과 값이 0인 것은 다르다."""
    summary = rework.summarize([_row(flagged=False, rework_ratio_h=0.2)])
    assert summary["by_signal"]["flagged"]["n"] == 0
    assert summary["by_signal"]["flagged"]["median"] is None


def test_sessions_without_a_ratio_are_not_scored():
    """기간이 모자란 세션은 비율이 없다. 0으로 세면 안 된다."""
    summary = rework.summarize([_row(rework_ratio_h=None)])
    assert summary["n_scored"] == 0
    assert summary["all"]["median"] is None


def test_sessions_that_changed_nothing_are_counted_separately():
    """아무것도 안 남긴 세션은 되돌림 0이 아니다. 따로 세야 보인다."""
    rows = [
        _row(flagged=True, added_lines=0, gone_lines=0, rework_ratio_h=None),
        _row(flagged=True, added_lines=40, rework_ratio_h=0.5),
        _row(flagged=False, added_lines=40, rework_ratio_h=0.1),
    ]
    summary = rework.summarize(rows)
    assert summary["n_changed_nothing"] == 1
    idle = summary["changed_nothing_by_signal"]
    assert idle["flagged"] == {"n": 2, "idle": 1, "rate": 0.5}
    assert idle["unflagged"] == {"n": 1, "idle": 0, "rate": 0.0}
    # 그 세션이 비율 평균을 0 쪽으로 끌어내리지 않았다.
    assert summary["by_signal"]["flagged"]["median"] == 0.5


def test_session_times_reads_the_transcript(tmp_path):
    path = tmp_path / "t.jsonl"
    path.write_text("\n".join([
        json.dumps({"timestamp": "2026-08-22T08:33:53.899Z"}),
        "not json at all",
        json.dumps({"no": "timestamp"}),
        json.dumps({"timestamp": "2026-08-22T08:44:10.602Z"}),
    ]), encoding="utf-8")
    first, last = rework.session_times({"transcript": str(path)})
    assert last - first == pytest.approx(616.703, abs=0.01)


def test_session_times_is_none_without_a_transcript():
    assert rework.session_times({"transcript": None}) is None
    assert rework.session_times({"transcript": "/nope/missing.jsonl"}) is None
