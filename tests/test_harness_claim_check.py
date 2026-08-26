"""사실 오류 되풀이 검사 테스트 (`harness/claim_check.py`, `harness/check_claims.py`).

**한 자리를 고치는 것으로는 같은 문장이 다시 나오는 것을 막지 못한다.**
2026-08-26에 실제로 그랬다: `harness/anchor.md` 가 옛 과제 열한 종을 한
문장으로 잘못 적었고, 그 문장이 다른 파일 다섯으로 옮겨 적혔으며, 세션이
그것을 검증 없이 유저에게 인용했다. 앵커를 고친 뒤에도 나머지 다섯이 남아
있었고 유저가 다시 물어서야 드러났다.

아래 시험은 그 두 경로를 고정한다 — 답에 다시 나오는 것(Stop 훅)과 파일에
다시 들어오는 것(pre-commit).
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "harness"


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HARNESS / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    if str(HARNESS) not in sys.path:
        sys.path.insert(0, str(HARNESS))
    spec.loader.exec_module(module)
    return module


claim_check = _load("casa_claim_check", "claim_check.py")
check_claims = _load("casa_check_claims", "check_claims.py")

RULES = claim_check.load_rules()


# ------------------------------------------------------------ 목록 자체


def test_rules_file_is_valid_and_non_empty():
    data = json.loads((HARNESS / "claim_rules.json").read_text(encoding="utf-8"))
    assert data["rules"], "목록이 비면 이 검사는 아무것도 막지 않는다"
    for rule in data["rules"]:
        # 항목 하나는 틀린 서술과 그 서술이 무엇에 대한 것인지의 짝이다.
        assert rule["pattern"] and rule["scope"]
        # 유저가 검증할 수 있어야 하므로 왜 틀렸는지와 대신 무엇을 적을지를 함께 둔다.
        assert rule["why"] and rule["instead"] and rule["source"]


# ------------------------------------------------- 실제로 있었던 문장들


def test_the_sentence_that_was_in_architecture_md_is_detected():
    text = '| 옛 11종 (`harness/legacy_tasks.txt`) | "함수 하나가 비어 있고 명세는 완전하다" | 면제 |'
    hits = claim_check.find_false_claims(text, RULES)
    assert len(hits) == 1
    assert "buggy-pipeline" in hits[0]["why"]


def test_the_sentence_the_session_quoted_to_the_user_is_detected():
    """2026-08-26 세션이 유저에게 보낸 문장 그대로."""
    text = "과제 11종이 전부 함수 하나 구현이라 판단·정합·규율 차원이 빠졌다."
    assert claim_check.find_false_claims(text, RULES)


def test_two_experiments_sentence_across_two_lines_is_detected():
    text = '기존 과제 11종은 구조가 하나다: "함수 하나가 비어 있고 명세는\n완전하니 테스트를 통과시켜라".'
    assert claim_check.find_false_claims(text, RULES)


# --------------------------------------------- 맞는 말까지 막으면 안 된다


def test_the_same_wording_about_new_tasks_is_not_flagged():
    """`harness/anchor.md` 의 "반복된 실수" 3번은 새 과제에 대한 규칙이다.

    같은 표현이 옛 과제 열한 종에 대해서는 틀리고 새로 만드는 과제에 대해서는
    맞다. 그래서 항목이 서술과 대상의 짝으로 되어 있다.
    """
    text = '방향을 틀어 새 과제를 만들 때, 그 과제가 또 "함수 하나 구현"이면\n아무것도 바뀌지 않은 것이다.'
    assert claim_check.find_false_claims(text, RULES) == []


def test_backticked_mention_is_skipped():
    """틀린 문장을 정정하는 글 자체가 차단되면 안 된다."""
    text = "열한 개에 `전부 함수 하나 구현` 이라고 적혀 있었는데 셋에 대해 틀렸다."
    assert claim_check.find_false_claims(text, RULES) == []


def test_scope_and_claim_in_different_paragraphs_do_not_match():
    text = "옛 과제 11종은 검문에서 면제된다.\n\n새 과제가 또 함수 하나 구현이면 소용이 없다."
    assert claim_check.find_false_claims(text, RULES) == []


# --------------------------------------------------- 저장소 전문 검사


def test_repo_files_carry_no_known_false_claim():
    """정정한 여섯 자리가 다시 틀린 문장으로 돌아가면 여기서 실패한다."""
    findings = check_claims.scan(check_claims.collect(ROOT), RULES)
    assert findings == {}, f"틀린 주장이 다시 들어왔다: {sorted(findings)}"


def test_history_file_is_not_scanned_in_full():
    """`STATUS.md` 의 지난 항목은 그때 그렇게 적었다는 사실 자체가 기록이다.

    `STATUS.md` 의 2026-08-19·08-26 항목은 그 시점에 무엇을 알고 있었는지를
    적은 것이고 틀린 문장을 인용문으로 담고 있다. 전문을 검사하면 그 기록을
    고쳐 쓰라는 요구가 되므로, 기록 파일은 **새로 더한 줄만** 본다.
    """
    assert "STATUS.md" in claim_check.load_history_files()
    full = (ROOT / "STATUS.md").read_text(encoding="utf-8")
    assert claim_check.find_false_claims(full, RULES), (
        "이 시험의 전제가 사라졌다 — STATUS.md 에 옛 인용문이 더는 없다면 "
        "기록 파일 예외 자체를 다시 볼 것"
    )
    assert check_claims.collect(ROOT).get("STATUS.md", "") != full


def test_scanned_paths_exclude_collected_output_and_task_repos():
    assert check_claims.is_scanned("docs/ARCHITECTURE.md")
    assert check_claims.is_scanned("harness/legacy_tasks.txt")
    assert not check_claims.is_scanned("results/main2/x/README.md")
    assert not check_claims.is_scanned("pilot/tasks/schedule/template/README.md")
    assert not check_claims.is_scanned("docs/plan.pdf")
    # 시험은 틀린 문장을 그대로 담아야 검사가 그것을 잡는지 확인할 수 있다.
    # 이 파일 자신이 그 예다 — 검사가 tests/ 를 보면 이 파일에 막힌다.
    assert not check_claims.is_scanned("tests/test_harness_claim_check.py")


# ------------------------------------------------------------ 훅의 동작


def _run_hook(payload: dict, env: dict | None = None) -> subprocess.CompletedProcess:
    """훅을 따로 실행한다.

    `encoding="utf-8"` 을 반드시 준다. 윈도우에서는 `text=True` 만 주면 자식의
    출력을 로캘 인코딩(cp1252)으로 읽으려다 한글에서 실패하고, `stderr` 가
    `None` 이 된다 — 2026-08-26에 이 시험이 CI 의 윈도우 두 조합에서만 그렇게
    실패했다.
    """
    return subprocess.run(
        [sys.executable, str(HARNESS / "claim_check.py")],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=False,
    )


def test_hook_blocks_a_repeated_false_claim_once_then_stays_quiet():
    payload = {
        "session_id": "claim-check-test-session",
        "last_assistant_message": "과제 11종이 전부 함수 하나 구현이라 차원이 빠졌다.",
    }
    marker = claim_check._marker(payload["session_id"])
    marker.unlink(missing_ok=True)
    try:
        first = _run_hook(payload)
        assert first.returncode == 2
        assert "claim_rules.json" in first.stderr
        second = _run_hook(payload)
        assert second.returncode == 0
    finally:
        marker.unlink(missing_ok=True)


def test_hook_passes_a_clean_answer():
    payload = {
        "session_id": "claim-check-clean-session",
        "last_assistant_message": "열한 종이 공유하는 것은 넷이다: 목표가 하나, 명세가 완전, "
        "산출물이 하나, 판정이 이진.",
    }
    assert _run_hook(payload).returncode == 0


def test_hook_survives_garbage_input():
    res = subprocess.run(
        [sys.executable, str(HARNESS / "claim_check.py")],
        input="not json",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert res.returncode == 0


def test_the_block_message_survives_a_non_utf8_console():
    """윈도우가 기본으로 cp949 로 내보낸다. 차단 사유가 한글이라 여기서 깨진다."""
    import os

    payload = {
        "session_id": "claim-check-cp949-probe",
        "last_assistant_message": "과제 11종이 전부 함수 하나 구현이라 차원이 빠졌다.",
    }
    marker = claim_check._marker(payload["session_id"])
    marker.unlink(missing_ok=True)
    try:
        res = _run_hook(payload, env=dict(os.environ, PYTHONIOENCODING="cp949"))
        assert res.returncode == 2
        assert "claim_rules.json" in res.stderr
    finally:
        marker.unlink(missing_ok=True)
