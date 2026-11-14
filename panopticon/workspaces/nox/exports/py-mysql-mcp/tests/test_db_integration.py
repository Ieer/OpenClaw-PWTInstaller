"""端到端：用 SQLite 跑通 query / execute（验证占位符与参数绑定链路）。

说明：本服务面向 MySQL，但执行层通过 SQLAlchemy 方言适配，故这里用 SQLite 做
「无 MySQL 依赖」的功能验证（SELECT/INSERT/UPDATE 及中文、特殊字符）。
"""

import pytest

from py_mysql_mcp.config import AppConfig
from py_mysql_mcp.db import ParamCountError, create_pool, execute_statement, query_rows


@pytest.fixture()
def engine(tmp_path):
    db_file = tmp_path / "demo.db"
    cfg = AppConfig(
        mysql_host="127.0.0.1",
        mysql_port=3306,
        mysql_user="root",
        mysql_password="",
        mysql_database=None,
        pool_size=5,
        read_only=False,
        http_host="127.0.0.1",
        http_port=3000,
        database_url=f"sqlite:///{db_file}",
    )
    eng = create_pool(cfg)
    yield eng
    eng.dispose()


def test_ddl_insert_select_update(engine):
    # DDL 的 rowcount 各家驱动不一致（MySQL=0 / SQLite=-1），故不在此断言
    execute_statement(engine, "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)")

    info = execute_statement(engine, "INSERT INTO users (name, age) VALUES (?, ?)", ["Alice", 30])
    assert info["affectedRows"] == 1
    assert "insertId" in info

    execute_statement(engine, "INSERT INTO users (name, age) VALUES (?, ?)", ["Bob", 17])

    rows = query_rows(engine, "SELECT id, name, age FROM users WHERE age > ? ORDER BY id", [18])
    assert len(rows) == 1
    assert rows[0]["name"] == "Alice"

    info = execute_statement(engine, "UPDATE users SET age = ? WHERE name = ?", [31, "Alice"])
    assert info["affectedRows"] == 1


def test_unicode_and_special_chars(engine):
    execute_statement(engine, "CREATE TABLE t (id INTEGER PRIMARY KEY, label TEXT)")
    execute_statement(engine, "INSERT INTO t (label) VALUES (?)", ["机械键盘 (test)"])
    rows = query_rows(engine, "SELECT label FROM t")
    assert rows[0]["label"] == "机械键盘 (test)"


def test_placeholder_mismatch_raises(engine):
    with pytest.raises(ParamCountError):
        query_rows(engine, "SELECT * FROM users WHERE id = ?", [])


def test_no_params_with_literal_placeholder_like_text(engine):
    execute_statement(engine, "CREATE TABLE t2 (id INTEGER PRIMARY KEY, name TEXT)")
    execute_statement(engine, "INSERT INTO t2 (name) VALUES (?)", ["100%"])
    rows = query_rows(engine, "SELECT name FROM t2")
    assert rows[0]["name"] == "100%"
