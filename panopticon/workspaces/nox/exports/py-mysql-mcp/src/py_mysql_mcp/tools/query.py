"""mysql_query 工具：执行返回结果集的语句（主要是 SELECT）。

对应 TS 版 ``src/tools/query.ts``。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, Optional

from ._shared import ok, tool_error
from ..db import query_rows
from ..guard import assert_readable_in_read_only

if TYPE_CHECKING:  # pragma: no cover
    from mcp.server.fastmcp import FastMCP
    from sqlalchemy.engine import Engine

    from ..config import AppConfig


def register_query_tool(mcp: "FastMCP", engine: "Engine", config: "AppConfig") -> None:
    @mcp.tool(
        name="mysql_query",
        description=(
            "Execute a SQL query that returns a result set (mainly SELECT) and return rows as JSON. "
            "Use parameterized placeholders (?) for user input to prevent SQL injection. "
            "In read-only mode, only SELECT/SHOW/DESCRIBE/EXPLAIN are allowed."
        ),
    )
    def mysql_query(
        sql: str,
        params: Optional[List[Any]] = None,
        database: Optional[str] = None,
    ) -> str:
        """执行返回结果集的 SQL。

        Args:
            sql: 要执行的 SQL 语句（如 ``SELECT * FROM users WHERE id = ?``）。
            params: 与 ``?`` 占位符按顺序对应的参数值。
            database: 可选，覆盖默认目标数据库。
        """
        try:
            assert_readable_in_read_only(sql, config)
            rows = query_rows(engine, sql, params, database)
            return ok({"success": True, "rowCount": len(rows), "rows": rows})
        except Exception as exc:  # noqa: BLE001 - 统一转成结构化错误
            raise tool_error(exc, "mysql_query", sql) from exc
