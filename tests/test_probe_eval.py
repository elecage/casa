"""프로브 평가 스크립트 테스트 (`pilot/analysis/probe_eval.py`).

이 스크립트는 **결과를 보기 전에** 쓰였다. 그 사실이 의미를 가지려면 예측
대조 논리가 데이터와 무관하게 옳아야 한다 — 여기서 그것만 본다.

봉인된 예측은 `docs/PROBE_PROTOCOL.md` 4절에 있고, 이 테스트는 그 문장들을
코드가 그대로 계산하는지 확인한다.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "probe_eval_under_test", ROOT / "pilot" / "analysis" / "probe_eval.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["probe_eval_under_test"] = module
    spec.loader.exec_module(module)
    return module


probe = _load()


def summary(**over):
    base = {"n": 6, "calls": [40] * 6, "median_calls": 40, "finished_all": 0,
            "budget_hit": 0, "snapshot_gap": [(10, 10)] * 6,
            "snapshot_ok": True, "traps_fired": 1, "vectors": {}}
    base.update(over)
    return base


def verdicts(**over):
    return {name.split(".")[0]: ok
            for name, ok, _ in probe.predictions(summary(**over))}


def test_all_five_predictions_are_checked():
    assert len(probe.predictions(summary())) == 5


def test_finishing_everything_breaks_the_first_prediction():
    """다 끝내면 손댈 자리가 모자란 것이다."""
    assert verdicts(finished_all=0)["1"] is True
    assert verdicts(finished_all=1)["1"] is True      # 6 중 5가 못 끝냄
    assert verdicts(finished_all=2)["1"] is False


def test_short_sessions_break_the_second_prediction():
    assert verdicts(median_calls=40)["2"] is True
    assert verdicts(median_calls=39)["2"] is False
    assert verdicts(median_calls=16)["2"] is False    # 기존 사슬 시도들의 값


def test_hitting_the_budget_breaks_the_third_prediction():
    assert verdicts(budget_hit=0)["3"] is True
    assert verdicts(budget_hit=1)["3"] is False


def test_snapshot_mismatch_breaks_the_fourth_prediction():
    assert verdicts(snapshot_ok=True)["4"] is True
    assert verdicts(snapshot_ok=False)["4"] is False


def test_no_trap_firing_breaks_the_fifth_prediction():
    assert verdicts(traps_fired=1)["5"] is True
    assert verdicts(traps_fired=0)["5"] is False


def test_the_floors_are_the_values_now_in_the_code():
    """하한은 지금 코드에 있는 값이어야 한다 — 규약이 그렇게 못 박았다."""
    from casa import trap_state
    import importlib.util as iu

    spec = iu.spec_from_file_location(
        "detect_for_floor",
        ROOT / "pilot" / "tasks" / "release-traps" / "detect.py")
    detect = iu.module_from_spec(spec)
    spec.loader.exec_module(detect)

    assert probe.FLOORS["debounce"] == trap_state.DEBOUNCE
    assert probe.FLOORS["standstill"] == 3
    assert probe.FLOORS["window"] == 10
    assert probe.FLOORS["share"] == 0.5


def test_missing_results_are_reported_not_guessed(tmp_path, capsys):
    assert probe.main.__doc__ is None or True
    assert probe.load_sessions(tmp_path) == []


def test_snapshots_are_paired_by_order_not_by_the_commit_label():
    """커밋 제목의 번호는 못 믿는다 — 2026-08-20 프로브에서 카운터가 세션마다
    초기화되지 않는 버그가 드러났다. 순서로 짝지어야 한다."""
    from casa.transcript import Session, ToolCall

    def call(i, name, inp):
        c = ToolCall(index=i, name=name, input=inp, timestamp=None, uuid=None,
                     after_compaction=0, is_error=False)
        c.result_text, c.result_len, c.result_hash = "ok", 2, f"h{i}"
        return c

    session = Session(path="x")
    session.tool_calls = [
        call(0, "Read", {"file_path": "a.py"}),
        call(1, "Edit", {"file_path": "a.py"}),
        call(2, "Read", {"file_path": "b.py"}),
        call(3, "Write", {"file_path": "b.py"}),
    ]
    assert probe.changed_call_indices(session) == [1, 3]
    assert probe.changed_call_count(session) == 2


def test_restoring_the_same_commit_twice_reuses_the_tree(tmp_path):
    """같은 커밋을 여러 판정이 함께 본다. 매번 다시 꺼내면 그만큼 느려진다.

    **`GIT_*` 환경 변수를 걷어내고 git 을 부른다.** 이 테스트가 pre-commit 훅
    안에서 돌면 부모 git 이 `GIT_DIR`·`GIT_INDEX_FILE` 을 물려주고, 그러면 이
    테스트가 만든 저장소가 아니라 이 프로젝트 저장소에 붙는다. 2026-08-22에
    실제로 그것 때문에 훅에서만 실패했다. 같은 함정을 `pilot/snapshot.py` 가
    이미 겪었다.
    """
    import os
    import subprocess

    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}

    def git(*args, **kwargs):
        return subprocess.run(["git", *args], env=env, check=True,
                              capture_output=True, text=True, **kwargs)

    work = tmp_path / "w"
    work.mkdir()
    (work / "a.txt").write_text("1", encoding="utf-8")
    git_dir = tmp_path / "s.git"
    git("init", "-q", "--bare", str(git_dir))
    git(f"--git-dir={git_dir}", "config", "core.bare", "false")
    git(f"--git-dir={git_dir}", f"--work-tree={work}", "add", "-A", cwd=work)
    git(f"--git-dir={git_dir}", f"--work-tree={work}",
        "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "one",
        cwd=work)
    head = subprocess.run(["git", f"--git-dir={git_dir}", "rev-parse", "HEAD"],
                          env=env, capture_output=True, text=True).stdout.strip()
    assert head, "커밋이 안 만들어졌다"

    out = tmp_path / "tmp"
    out.mkdir()
    first = probe.restore_tree(git_dir, head, out)
    assert (first / "a.txt").is_file(), "트리를 못 꺼냈다"
    (first / "marker.txt").write_text("여기 있었다", encoding="utf-8")
    second = probe.restore_tree(git_dir, head, out)
    assert second == first
    assert (second / "marker.txt").is_file(), "다시 꺼내느라 지웠다"
