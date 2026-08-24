"""봉인한 옛 수집 결과를 건드리는 것을 막는 훅 (`harness/legacy_guard.py`).

**왜 이 훅이 있나.** 유저 지시(2026-08-23) — "지금까지의 수집 결과들은 레거시로
별도 보관하고. 자꾸 네가 건드리면서 오래된 자료만 뒤지게 하면 안돼." 그날
세션이 옛 자료로 같은 분석을 여섯 번 되풀이했다. **문서에 적어 두는 것으로는
안 지켜진다는 것이 그날 확인됐으므로 코드로 막는다.**

이 파일이 못 박는 것 넷.

1. **경로 인자만 보면 안 된다.** 셸 명령 안에 들어 있어도 막아야 한다.
2. **새 수집 디렉토리(`results/`)는 막지 않는다.** 이름이 비슷하다고 막으면
   앞으로 모을 자료를 못 쓴다.
3. **봉인이 조용히 풀리면 안 된다.** 잠금 파일을 못 읽으면 통과가 아니라
   차단이다.
4. **막는 이유와 해제 조건이 차단 메시지에 들어간다.**
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness"))

import gates  # noqa: E402
import legacy_guard  # noqa: E402


def _run(payload: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "harness" / "legacy_guard.py")],
        input=payload, capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
    )


# ------------------------------------------------- 무엇을 가리키는가


def test_a_path_argument_is_caught():
    assert legacy_guard.mentions_sealed(
        {"file_path": "results-legacy/cut/keep/meta.json"}) == "results-legacy"


def test_a_shell_command_is_caught():
    """경로 인자만 보면 셸 명령이 빠져나간다."""
    assert legacy_guard.mentions_sealed(
        {"command": "ls results-legacy/cut"}) == "results-legacy"


def test_a_windows_separator_is_caught():
    assert legacy_guard.mentions_sealed(
        {"command": r"type results-legacy\cut\meta.json"}) == "results-legacy"


def test_a_nested_argument_is_caught():
    assert legacy_guard.mentions_sealed(
        {"edits": [{"file_path": "results-legacy/x"}]}) == "results-legacy"


def test_the_new_collection_directory_is_not_sealed():
    """앞으로 모을 자료는 `results/` 에 간다. 막으면 안 된다."""
    assert legacy_guard.mentions_sealed({"file_path": "results/new/meta.json"}) is None
    assert legacy_guard.mentions_sealed(
        {"command": "python pilot/run_chain.py --out results/new"}) is None


def test_unrelated_calls_are_not_caught():
    assert legacy_guard.mentions_sealed({"command": "python -m pytest"}) is None
    assert legacy_guard.mentions_sealed({"file_path": "src/casa/signals.py"}) is None


# ----------------------------------------------------- 훅으로 실행


def test_the_hook_blocks_while_sealed():
    """종료 코드 2가 실제로 도구 호출을 멈추게 한다."""
    if gates.gate_state("legacy") != "sealed":
        import pytest
        pytest.skip("legacy 게이트가 열려 있어 차단 경로가 해당 없음")
    res = _run(json.dumps({"tool_name": "Read",
                           "tool_input": {"file_path": "results-legacy/x.json"}}))
    assert res.returncode == 2
    assert "봉인" in res.stderr
    assert "해제 조건" in res.stderr


def test_the_block_message_survives_a_non_utf8_console():
    """윈도우가 기본으로 cp949 로 내보낸다. 그러면 차단 메시지가 깨진다.

    2026-08-23에 이것이 CI 의 윈도우 두 조합에서만 실패했다. 리눅스에서도
    같은 조건을 만들어 잡는다 — `PYTHONIOENCODING` 을 cp949 로 두고 부른다.
    """
    import os
    env = dict(os.environ, PYTHONIOENCODING="cp949")
    res = subprocess.run(
        [sys.executable, str(ROOT / "harness" / "legacy_guard.py")],
        input=json.dumps({"tool_name": "Read",
                          "tool_input": {"file_path": "results-legacy/x.json"}}),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, check=False,
    )
    if gates.gate_state("legacy") != "sealed":
        import pytest
        pytest.skip("legacy 게이트가 열려 있어 차단 경로가 해당 없음")
    assert res.returncode == 2
    assert "봉인" in res.stderr


def test_the_hook_passes_calls_that_do_not_touch_it():
    res = _run(json.dumps({"tool_name": "Bash",
                           "tool_input": {"command": "python -m pytest -q"}}))
    assert res.returncode == 0


def test_the_hook_survives_garbage_input():
    assert _run("not json at all").returncode == 0
    assert _run(json.dumps({"tool_name": "Bash"})).returncode == 0


# --------------------------------------------------------- 게이트 파일


def test_the_gate_file_declares_the_legacy_seal():
    data = json.loads((ROOT / "harness" / "gates.json").read_text(encoding="utf-8"))
    entry = data.get("legacy")
    assert isinstance(entry, dict)
    for key in ("state", "reason", "unseal_requires", "path"):
        assert entry.get(key), key


def test_a_missing_gate_entry_blocks_rather_than_passes(monkeypatch, capsys):
    """봉인이 조용히 무력화되면 안 된다 — 상태를 못 읽으면 막는다."""
    monkeypatch.setattr(legacy_guard, "load_gates", lambda: {})
    monkeypatch.setattr(
        "sys.stdin",
        __import__("io").StringIO(json.dumps(
            {"tool_name": "Read",
             "tool_input": {"file_path": "results-legacy/x.json"}})))
    assert legacy_guard.main() == 2
    assert "읽지 못했다" in capsys.readouterr().err


def test_an_open_gate_lets_the_call_through(monkeypatch):
    monkeypatch.setattr(legacy_guard, "load_gates",
                        lambda: {"legacy": {"state": "open"}})
    monkeypatch.setattr(
        "sys.stdin",
        __import__("io").StringIO(json.dumps(
            {"tool_name": "Read",
             "tool_input": {"file_path": "results-legacy/x.json"}})))
    assert legacy_guard.main() == 0
