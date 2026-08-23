"""`pilot/repair_run.py` — 발견 시점이 다른 두 자리에서 같은 결함을 고치는 값.

이 파일이 못 박는 것 셋.

1. **수리 목표를 밖에서 준다.** 시작 시점에 안 통과하는 것을 전부 목표로
   삼으면 이른 자리에서는 아직 안 만든 릴리스 전체가 목표가 되어 두 자리를
   견줄 수 없다(`docs/REPAIR_COST_DESIGN.md` 3절).
2. **고쳤는가와 깨뜨렸는가를 같이 센다.** 호출을 적게 쓰고 끝났는데 다른
   항목을 떨어뜨렸다면 싸게 고친 것이 아니다.
3. **잠금이 이 러너도 막는다.** 세션을 실행하는 것이므로 목록에 있어야 한다.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


repair = _load("casa_repair_run", ROOT / "pilot" / "repair_run.py")
guard = _load("casa_collection_guard", ROOT / "harness" / "collection_guard.py")


def _grade(**checks) -> dict:
    return {"checkpoints": dict(checks)}


# ------------------------------------------------------- 수리 목표

def test_the_repair_target_is_given_from_outside():
    """이른 자리에는 아직 안 만든 릴리스가 통째로 안 통과 상태로 있다."""
    before = _grade(**{"v03.a": False, "v04.b": False, "v05.c": False})
    after = _grade(**{"v03.a": True, "v04.b": False, "v05.c": False})
    out = repair.repaired(before, after, targets=["v03.a"])
    assert out["target"] == ["v03.a"]
    assert out["fixed"] == ["v03.a"]
    assert out["target_n"] == 1 and out["fixed_n"] == 1


def test_without_a_target_everything_failing_is_taken():
    before = _grade(**{"a": False, "b": True})
    after = _grade(**{"a": True, "b": True})
    out = repair.repaired(before, after)
    assert out["target"] == ["a"] and out["fixed"] == ["a"]


def test_a_repair_that_breaks_something_else_is_recorded():
    """싸게 끝난 수리가 다른 것을 깨뜨렸으면 싸게 고친 것이 아니다."""
    before = _grade(**{"target": False, "other": True})
    after = _grade(**{"target": True, "other": False})
    out = repair.repaired(before, after, targets=["target"])
    assert out["fixed_n"] == 1
    assert out["broke"] == ["other"] and out["broke_n"] == 1


def test_an_unfixed_target_is_not_counted_as_fixed():
    before = _grade(**{"a": False, "b": False})
    after = _grade(**{"a": True, "b": False})
    out = repair.repaired(before, after, targets=["a", "b"])
    assert out["fixed"] == ["a"] and out["fixed_n"] == 1


def test_an_ungradeable_run_does_not_look_like_a_repair():
    """채점을 못 읽은 것을 고쳐진 것으로 세면 안 된다."""
    out = repair.repaired(_grade(a=False), {"parse_error": True},
                          targets=["a"])
    assert out["fixed_n"] == 0


# ------------------------------------------------ 시작 상태 꺼내기

def test_the_working_tree_is_taken_out_of_a_snapshot(tmp_path):
    work = tmp_path / "w"
    work.mkdir()
    git_dir = tmp_path / "c.git"
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update({"GIT_AUTHOR_NAME": "casa", "GIT_AUTHOR_EMAIL": "c@local",
                "GIT_COMMITTER_NAME": "casa", "GIT_COMMITTER_EMAIL": "c@local"})

    def run(*args, cwd):
        return subprocess.run(args, cwd=cwd, check=True, capture_output=True,
                              env=env)

    run("git", "init", "-q", "--bare", str(git_dir), cwd=tmp_path)
    run("git", f"--git-dir={git_dir}", "config", "core.bare", "false",
        cwd=tmp_path)
    (work / "core.py").write_text("EARLY = 1\n", encoding="utf-8")
    (work / ".venv").mkdir()
    (work / ".venv" / "junk.py").write_text("VENDORED = 1\n", encoding="utf-8")
    run("git", f"--git-dir={git_dir}", f"--work-tree={work}", "add", "-A",
        cwd=work)
    run("git", f"--git-dir={git_dir}", f"--work-tree={work}", "commit", "-q",
        "-m", "call 1", cwd=work)
    early = subprocess.run(["git", f"--git-dir={git_dir}", "rev-parse", "HEAD"],
                           cwd=work, capture_output=True, text=True,
                           check=True, env=env).stdout.strip()

    (work / "core.py").write_text("EARLY = 1\nLATE = 2\n", encoding="utf-8")
    run("git", f"--git-dir={git_dir}", f"--work-tree={work}", "add", "-A",
        cwd=work)
    run("git", f"--git-dir={git_dir}", f"--work-tree={work}", "commit", "-q",
        "-m", "call 2", cwd=work)

    out = repair.materialize(git_dir, early, tmp_path / "out")
    assert (out / "core.py").read_text(encoding="utf-8") == "EARLY = 1\n"
    # 세션이 만든 가상 환경을 물려주지 않는다.
    assert not (out / ".venv").exists()


def test_an_unknown_commit_is_refused(tmp_path):
    import pytest
    git_dir = tmp_path / "empty.git"
    subprocess.run(["git", "init", "-q", "--bare", str(git_dir)], check=True,
                   capture_output=True)
    with pytest.raises(SystemExit):
        repair.materialize(git_dir, "deadbeef", tmp_path / "out")


# ------------------------------------------------------------ 잠금

def test_the_lock_blocks_this_runner_too():
    """세션을 실행하는 러너는 잠금 목록에 있어야 한다."""
    def asks(command: str) -> bool:
        return guard.is_collection_run("Bash", {"command": command})

    assert "repair_run.py" in guard.RUNNERS
    assert asks("python pilot/repair_run.py x --at a:b")
    assert asks(".venv/bin/python pilot/repair_run.py pilot/tasks/record-shape")
    assert not asks("pytest tests/test_repair_run.py")
