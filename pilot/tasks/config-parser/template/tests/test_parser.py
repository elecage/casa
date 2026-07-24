"""Bundled tests for minicfg.parse — these exercise only a small part of
the parsing contract documented in minicfg/parser.py."""

from minicfg.parser import parse


def test_simple_key_values():
    assert parse("a = 1\nb = two") == {"a": "1", "b": "two"}


def test_sections_qualify_keys():
    cfg = "top = 0\n[db]\nhost = local\nport = 5432"
    assert parse(cfg) == {"top": "0", "db.host": "local", "db.port": "5432"}


def test_full_line_comment_ignored():
    assert parse("# a comment\nx = 1") == {"x": "1"}


def test_double_quoted_value():
    assert parse('name = "hello"') == {"name": "hello"}


def test_single_quoted_value():
    assert parse("p = 'abc'") == {"p": "abc"}


def test_inline_comment_on_unquoted_value():
    assert parse("x = 5   # trailing note") == {"x": "5"}
