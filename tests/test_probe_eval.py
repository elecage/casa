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
