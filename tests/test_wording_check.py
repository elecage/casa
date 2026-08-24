"""글쓰기 규칙 위반을 세션 종료 직전에 확인하는 훅 (`harness/wording_check.py`).

**왜 이 훅이 있나.** 유저 물음(2026-08-24) — "네가 스스로 오류를 찾아내는 것이
아니고 나와의 인터랙션에 의해서 나오잖아. 이걸 네가 나인 것처럼 모사하는 훅을
만들 수 있냐는거야." 글로 적힌 규칙을 어긴 것은 답의 문자열 안에 그대로 있어
목록 대조로 판정된다.

이 파일이 못 박는 것 다섯.

1. **`CLAUDE.md` 표의 구어체와 비유가 실제로 검출된다.**
2. **백틱 안의 글자는 보지 않는다.** 그렇게 하지 않으면 위반을 정정하는 답
   자체가 차단된다 — 정정하려면 그 말을 이름으로 불러야 한다.
3. **'되돌린다' 는 '돌린다' 로 검출되지 않는다.** 되돌림 비용이 이 프로젝트의
   중심 용어라 잘못 검출되면 쓸 수 없다.
4. **분모를 안 밝힌 비율을 검출하고, 밝힌 비율은 통과시킨다.**
5. **목록 파일을 못 읽어도 세션을 막지 않는다.** 이 훅은 규율 검사이지 잠금이
   아니다.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness"))

import wording_check as wc  # noqa: E402


def _names(text: str) -> list[str]:
    return [hit["name"] for hit in wc.find_violations(text)]


# --------------------------------------------------- 목록에 있는 말을 검출한다


def test_the_colloquial_verbs_from_the_rule_table_are_caught():
    assert "재다" in _names("이 값을 잰다.")
    assert "돌리다" in _names("배치를 돌렸다.")
    assert "잘리다" in _names("세션이 잘렸다.")
    assert "걸리다" in _names("예산에 걸린다.")


def test_the_contracted_forms_are_caught():
    """한국어에서 `걸리`+`ㄴ다`는 `걸린다`가 되어 어간 글자가 남지 않는다.
    어간만 적은 첫 판이 이 형태를 전부 놓쳤다."""
    for sentence, expected in [("예산에 걸린다", "걸리다"),
                               ("한쪽으로 몰릴 수 있다", "몰리다"),
                               ("배치를 돌린다", "돌리다"),
                               ("세션이 잘린다", "잘리다"),
                               ("값이 갈릴 수 있다", "갈리다"),
                               ("뒤 항목이 막힌다", "막히다")]:
        assert expected in _names(sentence), sentence


def test_the_metaphors_from_the_rule_table_are_caught():
    assert "삼키다" in _names("한 세션이 항목을 삼킨다.")
    assert "죽어 있다" in _names("그 조건은 죽어 있다.")


def test_the_words_the_user_flagged_in_conversation_are_caught():
    """유저가 지적한 말 하나가 목록 항목 하나가 된다 — 이 파일이 있는 이유."""
    assert "쌓이다 / 쌓다" in _names("뒤 항목이 그 위에 쌓인다.")
    assert "갈리다" in _names("세션마다 값이 갈린다.")
    assert "몰리다" in _names("한쪽으로 몰린다.")
    assert "막히다" in _names("뒤 항목에서 막힌다.")
    assert "쳇바퀴" in _names("같은 얘기를 쳇바퀴 돈다.")
    assert "배터리 (지표 묶음)" in _names("지표 배터리를 더했다.")


#: 2026-08-24 세션이 유저에게 보낸 답에서 그대로 가져온 문장들. 유저가 이
#: 문장들을 지적했다.
#:
#: **이 시험이 필요한 이유.** 처음 판은 어미를 하나씩 적었고, 그래서 이 다섯 중
#: 셋을 검출하지 못했다 — `쌓이고`, `갈리던`, `부딪히고` 가 목록에 없었다.
#: 그런데 시험은 다 통과했다. 시험을 실제 사례가 아니라 구현에 맞춰 썼기
#: 때문이다. 실제로 지적받은 문장을 그대로 넣어야 그 실수가 검출된다.
REAL_SENTENCES = [
    ("뒤 항목이 그 위에 쌓이고, 바로잡으려면 쌓인 것을 다 다시 써야 한다",
     "쌓이다 / 쌓다"),
    ("그러면 세션마다 갈리던 행동이 한쪽으로 모인다", "갈리다"),
    ("완료 조건을 채우려다 그 결정에 부딪히고, 그러면 못 채운다", "부딪히다"),
    ("세션에게 맡기면 한쪽으로 몰릴 수 있어서 대조가 안 생긴다", "몰리다"),
    ("그것을 재는 유일한 과제이고 배치를 돌렸다", "재다"),
]


def test_the_sentences_the_user_actually_flagged_are_caught():
    for sentence, expected in REAL_SENTENCES:
        assert expected in _names(sentence), sentence


def test_a_bare_ratio_the_user_actually_flagged_is_caught():
    """'맞힌 세션 수는 47/48' 이 유저가 지적한 문장이다. '세션 수' 가 있다고
    분모를 밝힌 것으로 보면 안 된다."""
    assert wc.find_bare_ratios("맞힌 세션 수는 47/48 이다.") == ["47/48"]


def test_the_message_names_the_replacement():
    hits = wc.find_violations("이 값을 잰다.")
    body = wc.build_message(hits, [])
    assert "측정한다" in body


# ------------------------------------------------------------ 안 보는 자리


def test_a_word_inside_backticks_is_not_counted():
    """위반을 정정하려면 그 말을 이름으로 불러야 한다."""
    assert _names("`잰다` 대신 `측정한다` 를 쓴다.") == []


def test_a_fenced_block_is_not_counted():
    assert _names("설명\n```\n배치를 돌렸다\n```\n끝") == []


def test_a_quoted_line_is_not_counted():
    """유저의 말을 인용하는 것은 위반이 아니다."""
    assert _names("> 세션이 잘렸다\n\n확인했다.") == []


def test_undoing_is_not_mistaken_for_running():
    """되돌림 비용이 이 프로젝트의 중심 용어다. 잘못 검출되면 쓸 수 없다."""
    for sentence in ["앞 세션이 남긴 것을 되돌린다.", "뒤 세션이 되돌렸다.",
                     "되돌릴 수 있다.", "그 결과를 되돌려야 한다."]:
        assert "돌리다" not in _names(sentence), sentence


def test_blocking_a_call_is_not_the_banned_word():
    """훅이 호출을 막는 것은 규칙에 해당하지 않는다."""
    assert "막히다" not in _names("이 훅이 그 호출을 막는다.")


def test_ordinary_prose_passes():
    assert _names("세션 마흔여덟을 실행해 호출 수의 중앙값을 산출한다.") == []


# --------------------------------------------------------- 분모 없는 비율


def test_a_bare_ratio_is_caught():
    assert wc.find_bare_ratios("맞힌 세션은 47/48 이다.") == ["47/48"]


def test_a_ratio_that_states_its_denominator_passes():
    assert wc.find_bare_ratios("판정한 48세션 중 47세션을 맞혔다.") == []
    assert wc.find_bare_ratios("48세션 중 47/48 을 맞혔다.") == []


def test_a_version_pair_is_not_a_ratio():
    assert wc.find_bare_ratios("파이썬 3.10/3.13 에서 실행한다.") == []


def test_a_path_is_not_a_ratio():
    assert wc.find_bare_ratios("결과는 results/2026 에 있다.") == []


def test_a_ratio_inside_backticks_is_not_counted():
    assert wc.find_bare_ratios("`47/48` 로 적혀 있다.") == []


# ------------------------------------------------------------- 훅으로 실행


def _run(payload: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "harness" / "wording_check.py")],
        input=payload, capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
    )


def test_the_hook_blocks_a_violating_answer(tmp_path, monkeypatch):
    monkeypatch.setattr(wc, "_marker", lambda _sid: tmp_path / "m")
    monkeypatch.setattr(
        "sys.stdin",
        __import__("io").StringIO(json.dumps(
            {"last_assistant_message": "배치를 돌렸고 세션마다 값이 갈린다."})))
    assert wc.main() == 2


def test_the_hook_blocks_only_once_per_session(tmp_path, monkeypatch):
    marker = tmp_path / "m"
    monkeypatch.setattr(wc, "_marker", lambda _sid: marker)
    payload = json.dumps({"last_assistant_message": "배치를 돌렸다."})
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(payload))
    assert wc.main() == 2
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(payload))
    assert wc.main() == 0


def test_the_hook_does_not_recurse_on_its_own_block():
    res = _run(json.dumps({"last_assistant_message": "배치를 돌렸다.",
                           "stop_hook_active": True}))
    assert res.returncode == 0


def test_the_hook_passes_a_clean_answer():
    assert _run(json.dumps(
        {"last_assistant_message": "세션 마흔여덟을 실행한다."})).returncode == 0


def test_the_hook_survives_garbage_input():
    assert _run("not json at all").returncode == 0
    assert _run(json.dumps({"last_assistant_message": ""})).returncode == 0
    assert _run(json.dumps({})).returncode == 0


def test_the_block_message_survives_a_non_utf8_console():
    """윈도우가 기본으로 cp949 로 내보낸다. 2026-08-23에 같은 결함이 CI 의
    윈도우 두 조합에서만 실패했다."""
    import os
    env = dict(os.environ, PYTHONIOENCODING="cp949")
    res = subprocess.run(
        [sys.executable, str(ROOT / "harness" / "wording_check.py")],
        input=json.dumps({"last_assistant_message": "배치를 돌렸다.",
                          "session_id": "cp949-probe"}),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, check=False,
    )
    if res.returncode == 0:
        import pytest
        pytest.skip("이 세션 표시가 이미 있어 차단 경로가 해당 없음")
    assert "글쓰기 규칙" in res.stderr


# ------------------------------------------------------------- 목록 파일


def test_the_rules_file_is_readable_and_every_rule_is_complete():
    rules = wc.load_rules()
    assert rules, "목록이 비어 있다"
    for rule in rules:
        for key in ("name", "kind", "instead", "source"):
            assert rule.get(key), rule


def test_an_unreadable_rules_file_does_not_block_the_session(tmp_path):
    """이 훅은 규율 검사이지 잠금이 아니다."""
    assert wc.load_rules(tmp_path / "없는파일.json") == []


def test_a_broken_pattern_does_not_disable_the_rest(tmp_path):
    path = tmp_path / "rules.json"
    path.write_text(json.dumps({"rules": [
        {"name": "깨진 것", "pattern": "([", "kind": "x", "instead": "y"},
        {"name": "멀쩡한 것", "pattern": "돌렸다", "kind": "구어체",
         "instead": "실행했다"},
    ]}), encoding="utf-8")
    assert [r["name"] for r in wc.load_rules(path)] == ["멀쩡한 것"]


def test_the_gate_entry_declares_this_check():
    data = json.loads((ROOT / "harness" / "gates.json").read_text(encoding="utf-8"))
    entry = data.get("wording_check")
    assert isinstance(entry, dict)
    assert entry.get("state") and entry.get("reason")


def test_the_hook_is_registered_in_settings():
    text = (ROOT / ".claude" / "settings.json").read_text(encoding="utf-8")
    assert "wording_check" in text
