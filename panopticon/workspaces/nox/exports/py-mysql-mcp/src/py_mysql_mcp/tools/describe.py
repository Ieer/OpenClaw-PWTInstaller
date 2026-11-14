"""mysql_describe 工具：查看表的列定义。

对应 TS 版 ``src/tools/describe.ts``。表名走白名单校验后内联（DESCRIBE 不支持占位符）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from ._shared import ok, tool_error
from ..db import query_rows
from ..guard import sanitize_identifier

if TYPE_CHECKING:  # pragma: no cover
    from mcp.server.fastmcp import FastMCP
    from sqlalchemy.engine import Engine

    from ..config import AppConfig

_INFO_SQL = (
    "SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY, COLUMN_DEFAULT, EXTRA, COLUMN_COMMENT "
    "FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ? ORDER BY ORDINAL_POSITION"
)


def register_describe_tool(mcp: "FastMCP", engine: "Engine", config: "AppConfig") -> None:
    @mcp.tool(
        name="mysql_describe",
        description=(
            "Describe the column definitions of a table (field name, type, null, key, default, extra). "
            "Helps the model understand table structure before writing SQL."
        ),
    )
    def mysql_describe(table: str, database: Optional[str] = None) -> str:
        """查看表结构。

        Args:
            table: 表名（如 ``users``）。
            database: 可选，覆盖默认目标数据库。
        """
        try:
            safe_table = sanitize_identifier(table)
            rows = query_rows(engine, f"DESCRIBE `{safe_table}`", [], database)

            target_db = database or config.mysql_database
            columns = rows
            if target_db:
                try:
                    rich = query_rows(engine, _INFO_SQL, [target_db, safe_table], None)
                    if rich:
                        columns = rich
                except Exception:  # noqa: BLE001 - information_schema 不可用时降级
                    columns = rows

            return ok({"success": True, "database": target_db, "table": safe_table, "columns": columns})
        except Exception as exc:  # noqa: BLE001
            raise tool_error(exc, "mysql_describe", f"[describe {table}]") from exc
