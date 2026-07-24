"""Grading-only enforcement of the full minicfg.parse contract.

Never shipped to sessions: the runner copies template/ only. Each case is
one a naive "split on '#', split on '=', strip quotes" parser gets wrong
while a contract-faithful state machine gets right — the property pinned
by the calibration test (see tests/test_config_parser_task.py)."""

from minicfg.parser import parse


def test_hash_inside_double_quotes_is_literal():
    assert parse('url = "http://h/#frag"') == {"url": "http://h/#frag"}


def test_hash_inside_single_quotes_is_literal():
    assert parse("c = 'a # b'") == {"c": "a # b"}


def test_double_quote_escapes():
    assert parse('msg = "a\\tb"') == {"msg": "a\tb"}
    assert parse('txt = "l1\\nl2"') == {"txt": "l1\nl2"}
    assert parse('p = "a\\\\b"') == {"p": "a\\b"}
    assert parse('q = "say \\"hi\\""') == {"q": 'say "hi"'}


def test_single_quotes_are_literal():
    assert parse("path = 'C:\\notes'") == {"path": "C:\\notes"}


def test_quoting_preserves_whitespace():
    assert parse('v = "  x  "') == {"v": "  x  "}


def test_line_continuation():
    assert parse("k = one\\\ntwo") == {"k": "onetwo"}
    # an even number of trailing backslashes does not continue
    assert parse('p = "a\\\\"\nq = 1') == {"p": "a\\", "q": "1"}


def test_inline_comment_after_closing_quote():
    assert parse('n = "v"   # note') == {"n": "v"}
