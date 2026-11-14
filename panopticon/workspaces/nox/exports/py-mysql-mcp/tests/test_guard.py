import pytest

from py_mysql_mcp.config import AppConfig
from py_mysql_mcp.guard import (
    GuardError,
    assert_execute_allowed,
    assert_readable_in_read_only,
    get_sql_first_keyword,
    is_read_only_sql,
    sanitize_identifier,
)


def _cfg(read_only: bool) -> AppConfig:
    return AppConfig(
        mysql_host="h",
        mysql_port=3306,
        mysql_user="u",
        mysql_password="p",
        mysql_database=None,
        pool_size=5,
        read_only=read_only,
        http_host="127.0.0.1",
        http_port=3000,
    )


@pytest.mark.parametrize(
    "sql,expected",
    [
        ("SELECT * FROM t", "SELECT"),
        ("  select 1", "SELECT"),
        ("/* c */ SELECT 1", "SELECT"),
        ("-- comment\nDELETE FROM t", "DELETE"),
        ("# hash comment\nUPDATE t SET a=1", "UPDATE"),
        ("", ""),
    ],
)
def test_first_keyword(sql, expected):
    assert get_sql_first_keyword(sql) == expected


@pytest.mark.parametrize("sql", ["SELECT 1", "show tables", "DESCRIBE t", "EXPLAIN SELECT 1", "desc t"])
def test_read_only_true(sql):
    assert is_read_only_sql(sql) is True


@pytest.mark.parametrize("sql", ["INSERT INTO t VALUES (1)", "UPDATE t SET a=1", "DROP TABLE t"])
def test_read_only_false(sql):
    assert is_read_only_sql(sql) is False


def test_query_guard_blocks_write_in_read_only():
    with pytest.raises(GuardError):
        assert_readable_in_read_only("DELETE FROM t", _cfg(True))
    # read-only 模式下 SELECT 放行
    assert_readable_in_read_only("SELECT 1", _cfg(True))


def test_query_guard_allows_write_when_not_read_only():
    assert_readable_in_read_only("DELETE FROM t", _cfg(False))


def test_execute_disabled_in_read_only():
    with pytest.raises(GuardError):
        assert_execute_allowed("INSERT INTO t VALUES (1)", _cfg(True))
    assert_execute_allowed("INSERT INTO t VALUES (1)", _cfg(False))


@pytest.mark.parametrize("name", ["users", "app.users", "t_1"])
def test_sanitize_identifier_ok(name):
    assert sanitize_identifier(name) == name


@pytest.mark.parametrize("name", ["users; DROP TABLE x", "a b", "1bad", "users`", ""])
def test_sanitize_identifier_rejects(name):
    with pytest.raises(GuardError):
        sanitize_identifier(name)
