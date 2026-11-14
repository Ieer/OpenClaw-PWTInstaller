import pytest

from py_mysql_mcp.sqlparams import (
    convert_placeholders,
    count_placeholders,
)


def test_count_placeholders_basic():
    assert count_placeholders("SELECT * FROM t WHERE a=? AND b=?") == 2
    assert count_placeholders("SELECT 1") == 0


def test_qmark_ignored_inside_string():
    assert count_placeholders("SELECT * FROM t WHERE name='a?b' AND id=?") == 1


def test_qmark_ignored_inside_comment_and_backtick():
    assert count_placeholders("SELECT `we?ird` FROM t -- x?\n WHERE id=?") == 1
    assert count_placeholders("SELECT `we?ird` FROM t WHERE id=?") == 1
    assert count_placeholders("SELECT /* ? */ 1 FROM t WHERE id=?") == 1


def test_convert_qmark_style_kept():
    sql = "SELECT * FROM t WHERE id=?"
    assert convert_placeholders(sql, "qmark", has_params=True) == sql


def test_convert_format_style():
    sql = "SELECT * FROM t WHERE id=? AND name=?"
    assert convert_placeholders(sql, "format", has_params=True) == "SELECT * FROM t WHERE id=%s AND name=%s"


def test_convert_format_escapes_percent():
    sql = "SELECT * FROM t WHERE name LIKE 'a%' AND id=?"
    out = convert_placeholders(sql, "format", has_params=True)
    assert out == "SELECT * FROM t WHERE name LIKE 'a%%' AND id=%s"


def test_convert_format_no_params_keeps_percent():
    sql = "SELECT * FROM t WHERE name LIKE 'a%'"
    assert convert_placeholders(sql, "format", has_params=False) == sql


def test_convert_skips_string_literal():
    sql = "SELECT * FROM t WHERE a='x?y' AND b=?"
    assert convert_placeholders(sql, "format", has_params=True) == "SELECT * FROM t WHERE a='x?y' AND b=%s"


def test_doubled_quote_escape():
    # 'it''s ?' 里的 ? 属于字符串
    sql = "SELECT * FROM t WHERE a='it''s ?' AND b=?"
    assert count_placeholders(sql) == 1


def test_unsupported_paramstyle():
    with pytest.raises(ValueError):
        convert_placeholders("SELECT ?", "named", has_params=True)
