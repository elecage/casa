"""호출 단위 스냅숏 테스트 (`pilot/snapshot.py`).

세 가지를 못 박는다.

1. **세션 쪽에는 흔적이 남지 않는다.** 세션이 쓰는 저장소에 우리 커밋이
   섞이면 세션이 `git log`에서 그것을 본다. 관측이 관측 대상을 바꾸면 안 된다.
2. **셸로 바꾼 파일도 잡힌다.** 편집 도구 호출만 따라가면 `sed`나
   `python -c` 로 바꾼 것이 샌다.
3. **세션을 절대 막지 않는다.** 설정이 없거나 깨져 있어도 0으로 끝난다.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

PILOT = Path(__file__).resolve().parents[1] / "pilot"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


snapshot = _load("casa_pilot_snapshot", PILOT / "snapshot.py")


def _git(*args, cwd=None):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


@pytest.fixture
def workdir(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    (work / "a.py").write_text("print(1)\n", encoding="utf-8")
    _git("init", "-q", "-b", "main", cwd=work)
    _git("-c", "user.name=t", "-c", "user.email=t@t", "add", "-A", cwd=work)
    _git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
         "-m", "initial", cwd=work)
    snapshot.install(work, tmp_path / "snapshots" / "work.git")
    return work


def test_a_change_is_committed_to_the_side_repository(workdir, tmp_path):
    (workdir / "a.py").write_text("print(2)\n", encoding="utf-8")
    assert snapshot.take(workdir) is not None

    log = _git(f"--git-dir={tmp_path / 'snapshots' / 'work.git'}",
               "log", "--oneline")
    assert "call 1" in log.stdout


def test_the_session_repository_is_left_alone(workdir):
    (workdir / "a.py").write_text("print(2)\n", encoding="utf-8")
    snapshot.take(workdir)

    log = _git("log", "--oneline", cwd=workdir)
    assert log.stdout.count("\n") == 1          # 세션이 만든 커밋 하나뿐
    assert "call" not in log.stdout
    status = _git("status", "--porcelain", cwd=workdir)
    assert "a.py" in status.stdout              # 세션 쪽에서는 여전히 미커밋


def test_shell_edits_are_caught_too(workdir, tmp_path):
    """편집 도구를 안 거친 변경도 잡혀야 한다."""
    subprocess.run([sys.executable, "-c",
                    "from pathlib import Path;"
                    "Path('a.py').write_text('print(3)\\n', encoding='utf-8')"],
                   cwd=workdir, check=True)
    assert snapshot.take(workdir) is not None
    show = _git(f"--git-dir={tmp_path / 'snapshots' / 'work.git'}",
                "show", "HEAD:a.py")
    assert show.stdout.strip() == "print(3)"


def test_nothing_changed_means_no_commit(workdir):
    (workdir / "a.py").write_text("print(2)\n", encoding="utf-8")
    assert snapshot.take(workdir) is not None
    assert snapshot.take(workdir) is None       # 두 번째는 찍을 것이 없다


def test_our_own_config_files_are_not_snapshotted(workdir, tmp_path):
    (workdir / "a.py").write_text("print(2)\n", encoding="utf-8")
    snapshot.take(workdir)
    listing = _git(f"--git-dir={tmp_path / 'snapshots' / 'work.git'}",
                   "ls-tree", "-r", "--name-only", "HEAD")
    assert "a.py" in listing.stdout
    assert ".casa-snapshot.json" not in listing.stdout
    assert ".claude" not in listing.stdout


def test_install_merges_into_existing_settings(tmp_path):
    """사슬 러너가 써 둔 예산 훅을 덮어쓰면 안 된다."""
    work = tmp_path / "w"
    (work / ".claude").mkdir(parents=True)
    (work / ".claude" / "settings.json").write_text(json.dumps(
        {"hooks": {"PreToolUse": [{"matcher": "*", "hooks": []}]}}),
        encoding="utf-8")

    snapshot.install(work, tmp_path / "s.git")

    settings = json.loads((work / ".claude" / "settings.json").read_text(
        encoding="utf-8"))
    assert "PreToolUse" in settings["hooks"]
    assert "PostToolUse" in settings["hooks"]


def test_the_hook_never_fails_a_session(tmp_path):
    """설정이 없어도 0으로 끝나야 한다 — 관측이 세션을 죽이면 안 된다."""
    done = subprocess.run([sys.executable, str(PILOT / "snapshot.py")],
                          cwd=tmp_path, input="{}", capture_output=True,
                          text=True, encoding="utf-8", errors="replace")
    assert done.returncode == 0


def test_take_without_configuration_is_a_no_op(tmp_path):
    assert snapshot.take(tmp_path) is None


def test_both_runners_wire_the_snapshot_hook():
    """배선이 조용히 빠지면 트리 계열 함정을 호출마다 볼 수 없게 된다."""
    for name in ("run_sessions.py", "run_chain.py"):
        source = (PILOT / name).read_text(encoding="utf-8")
        assert "snapshot.install" in source, name


def test_the_chain_runner_installs_snapshots_after_the_budget_hook():
    """예산 훅이 먼저 settings.json 을 쓰므로 순서가 뒤바뀌면 덮인다."""
    source = (PILOT / "run_chain.py").read_text(encoding="utf-8")
    assert source.index("install_budget(workdir") < source.index("snapshot.install")


def test_budget_and_snapshot_hooks_coexist(tmp_path):
    """둘 다 settings.json 을 쓴다. 어느 쪽이 먼저 와도 남아 있어야 한다."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "casa_pilot_budget", PILOT / "chain_budget.py")
    budget = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(budget)

    work = tmp_path / "w"
    work.mkdir()
    budget.install(work, 100)
    snapshot.install(work, tmp_path / "s.git")

    settings = json.loads((work / ".claude" / "settings.json").read_text(
        encoding="utf-8"))
    assert "PreToolUse" in settings["hooks"]
    assert "PostToolUse" in settings["hooks"]
    assert (work / ".casa-chain.json").is_file()


def test_the_single_session_runner_takes_a_budget():
    source = (PILOT / "run_sessions.py").read_text(encoding="utf-8")
    assert "chain_budget.install(workdir, budget)" in source
    assert '"--budget"' in source


def test_the_call_counter_starts_over_for_each_session(tmp_path):
    """번호는 세션마다 1부터다.

    2026-08-20 프로브에서 세어 두는 파일이 여러 세션이 공유하는 디렉토리에
    있어 번호가 세션 경계를 넘어 계속 올라갔다. 데이터는 멀쩡했지만 그
    이름표를 믿은 분석은 통째로 어긋난다.
    """
    first, second = tmp_path / "one", tmp_path / "two"
    for work in (first, second):
        work.mkdir()
        (work / "a.py").write_text("print(1)\n", encoding="utf-8")

    snapshot.install(first, tmp_path / "snapshots" / "one.git")
    snapshot.install(second, tmp_path / "snapshots" / "two.git")

    (first / "a.py").write_text("print(2)\n", encoding="utf-8")
    one = snapshot.take(first)
    (second / "a.py").write_text("print(3)\n", encoding="utf-8")
    two = snapshot.take(second)
    assert one and two, (one, two)

    for name in ("one", "two"):
        log = _git(f"--git-dir={tmp_path / 'snapshots' / f'{name}.git'}",
                   "log", "--format=%s")
        assert log.stdout.strip() == "call 1", (name, log.stdout, log.stderr)


def test_both_runners_take_a_final_snapshot():
    """세션의 마지막 편집을 훅이 못 잡고 끝나는 수가 있다.

    2026-08-20 프로브에서 여섯 중 하나가 그랬다 — 마지막 STATUS.md 편집이
    스냅숏에 안 들어갔다. 세션이 끝난 뒤 한 번 더 찍는다.
    """
    for name in ("run_sessions.py", "run_chain.py"):
        source = (PILOT / name).read_text(encoding="utf-8")
        assert "snapshot.take(workdir)" in source, name


def test_it_works_inside_a_git_hook_environment(workdir, tmp_path, monkeypatch):
    """git 훅 안에서 돌 때도 스냅숏이 담겨야 한다.

    부모 git 이 GIT_INDEX_FILE 을 물려주면 `add` 가 남의 색인에 담기고,
    스냅숏 저장소에는 담을 것이 없어 커밋이 조용히 실패한다. 2026-08-20에
    이것 때문에 커밋 훅에서만 스냅숏이 비었다 — 손으로 돌릴 때는 멀쩡했다.
    """
    monkeypatch.setenv("GIT_INDEX_FILE", str(tmp_path / "someone-elses.index"))
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "someone-elses.git"))

    (workdir / "a.py").write_text("print(9)\n", encoding="utf-8")
    assert snapshot.take(workdir) is not None
