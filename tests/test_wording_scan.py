"""트랜스크립트에 글쓰기 규칙 검사를 실행하는 도구 (`harness/wording_scan.py`).

**왜 있나.** 목록을 고칠 때 그 목록이 실제 글에서 무엇을 검출하는지 봐야 한다.
2026-08-24에 이 도구로 목록 첫 판을 확인했고 오검출 셋을 찾아 좁혔다 —
`돌려준다`(값을 반환한다), `프록시가 막혔다`, `둘로 갈라 적는다`.

이 파일이 못 박는 것 넷.

1. **세션이 유저에게 보낸 글만 본다.** 도구 호출과 유저의 말은 빼야 한다 —
   유저의 구어체를 세션의 위반으로 세면 안 된다.
2. **항목마다 몇 번인지와 표본을 같이 낸다.** 수만 내면 오검출인지 확인할 수
   없다.
3. **좁힌 규칙이 정상 표현을 통과시킨다.**
4. **기록을 못 읽어도 예외로 죽지 않는다.**
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness"))

import wording_scan as ws  # noqa: E402


def _write(tmp_path: Path, rows: list[dict]) -> Path:
    path = tmp_path / "t.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n또 깨진 줄\n",
                    encoding="utf-8")
    return path


def _assistant(text: str) -> dict:
    return {"message": {"role": "assistant",
                        "content": [{"type": "text", "text": text}]}}


def _user(text: str) -> dict:
    return {"message": {"role": "user",
                        "content": [{"type": "text", "text": text}]}}


def _tool_use() -> dict:
    return {"message": {"role": "assistant", "content": [
        {"type": "tool_use", "name": "Bash", "input": {"command": "배치를 돌렸다"}}]}}


# ------------------------------------------------------- 무엇을 읽는가


def test_only_the_answers_the_session_sent_are_read(tmp_path):
    """유저의 구어체를 세션의 위반으로 세면 안 된다."""
    path = _write(tmp_path, [_assistant("배치를 돌렸다."),
                             _user("그거 돌려봐."),
                             _tool_use()])
    assert ws.assistant_messages(path) == ["배치를 돌렸다."]


def test_a_broken_line_does_not_stop_the_scan(tmp_path):
    path = _write(tmp_path, [_assistant("이 값을 잰다.")])
    assert len(ws.assistant_messages(path)) == 1


def test_a_missing_transcript_is_not_fatal(tmp_path):
    assert ws.assistant_messages(tmp_path / "없는파일.jsonl") == []


# ----------------------------------------------------------- 세는 것


def test_the_scan_counts_per_rule_and_keeps_a_sample():
    result = ws.scan(["배치를 돌렸다.", "이 값을 잰다.", "배치를 또 돌렸다."])
    assert result["messages"] == 3
    assert result["flagged"] == 3
    assert result["counts"]["돌리다"] == 2
    assert result["samples"]["돌리다"], "표본이 없으면 오검출을 확인할 수 없다"


def test_the_scan_counts_bare_ratios_once_per_answer():
    result = ws.scan(["맞힌 세션 수는 47/48 이고 다른 것은 12/20 이다."])
    assert result["counts"]["분모 없는 비율"] == 2


def test_the_rendering_states_both_numbers():
    body = ws.render(ws.scan(["배치를 돌렸다.", "깨끗한 문장이다."]))
    assert "1개" in body and "2개" in body


# ------------------------------------------- 좁힌 규칙이 정상 표현을 통과시킨다


def test_the_narrowed_rules_pass_ordinary_technical_korean():
    """2026-08-24에 실제 기록에서 찾은 오검출들."""
    clean = [
        "그 함수는 위반 목록을 돌려준다.",
        "프록시가 막혀서 요청이 실패했다.",
        "남은 것을 둘로 갈라 적는다.",
        "앞 세션이 남긴 것을 되돌린다.",
        "그 훅이 호출을 막는다.",
        "설치에 시간이 걸린다.",
    ]
    result = ws.scan(clean)
    assert result["flagged"] == 0, result["counts"]


def test_the_narrowed_rules_still_catch_the_banned_use():
    caught = [
        "예산에 걸린다.",
        "세션마다 값이 갈린다.",
        "완료 조건이 막힌다.",
        "배치를 돌린다.",
    ]
    assert ws.scan(caught)["flagged"] == 4


# ------------------------------------------------------------- 명령줄


def test_the_command_line_reports_a_missing_transcript(tmp_path, capsys):
    assert ws.main([str(tmp_path / "없는파일.jsonl")]) == 1
    assert "경로" in capsys.readouterr().out


def test_the_command_line_runs(tmp_path, capsys):
    path = _write(tmp_path, [_assistant("배치를 돌렸다.")])
    assert ws.main([str(path), "--samples", "1"]) == 0
    assert "돌리다" in capsys.readouterr().out
