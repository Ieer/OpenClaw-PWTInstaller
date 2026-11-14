"""mysql_execute 工具：执行 DDL / DML（不返回结果集）。

对应 TS 版 ``src/tools/execute.ts``。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, Optional

from ._shared import ok, tool_error
from ..db import execute_statement
from ..guard import assert_execute_allowed

if TYPE_CHECKING:  # pragma: no cover
    from mcp.server.fastmcp import FastMCP
    from sqlalchemy.engine import Engine

    from ..config import AppConfig


def register_execute_tool(mcp: "FastMCP", engine: "Engine", config: "AppConfig") -> None:
    @mcp.tool(
        name="mysql_execute",
        description=(
            "Execute a DDL (CREATE/ALTER/DROP) or DML (INSERT/UPDATE/DELETE) statement that does not "
            "return a result set. Returns affectedRows / insertId metadata. "
            "Completely disabled in read-only mode. "
            "Use parameterized placeholders (?) for user input to prevent SQL injection."
        ),
    )
    def mysql_execute(
        sql: str,
        params: Optional[List[Any]] = None,
        database: Optional[str] = None,
    ) -> str:
        """执行 DDL/DML 语句。

        Args:
            sql: 要执行的 SQL 语句（如 ``INSERT INTO users (name) VALUES (?)``）。
            params: 与 ``?`` 占位符按顺序对应的参数值。
            database: 可选，覆盖默认目标数据库。
        """
        try:
            assert_execute_allowed(sql, config)
            info = execute_statement(engine, sql, params, database)
            return ok({"success": True, **info})
        except Exception as exc:  # noqa: BLE001
            raise tool_error(exc, "mysql_execute", sql) from exc
