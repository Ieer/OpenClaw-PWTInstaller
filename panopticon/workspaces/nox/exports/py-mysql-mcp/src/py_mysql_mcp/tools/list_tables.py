"""mysql_list 工具：列出所有数据库或指定库下的表。

对应 TS 版 ``src/tools/list.ts``。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from ._shared import ok, tool_error
from ..db import query_rows

if TYPE_CHECKING:  # pragma: no cover
    from mcp.server.fastmcp import FastMCP
    from sqlalchemy.engine import Engine

    from ..config import AppConfig


def register_list_tool(mcp: "FastMCP", engine: "Engine", config: "AppConfig") -> None:
    @mcp.tool(
        name="mysql_list",
        description=(
            "List all databases or all tables in a database. "
            'Use type="databases" to list all databases, or type="tables" with a database name '
            "to list tables."
        ),
    )
    def mysql_list(type: str, database: Optional[str] = None) -> str:
        """列出数据库或表。

        Args:
            type: ``"databases"`` 列出所有数据库；``"tables"`` 列出指定库的表。
            database: 当 ``type="tables"`` 时的目标数据库（可选，默认用连接配置的库）。
        """
        try:
            if type not in ("databases", "tables"):
                raise ValueError('[mysql_list] `type` must be "databases" or "tables".')

            if type == "databases":
                sql, target_db = "SHOW DATABASES", None
            else:
                target_db = database or config.mysql_database
                if not target_db:
                    raise ValueError(
                        '[mysql_list] When type="tables", a database name is required. '
                        "Provide the `database` parameter or configure MYSQL_DATABASE in .env."
                    )
                sql = "SHOW TABLES"

            rows = query_rows(engine, sql, [], target_db)
            items = [next(iter(row.values())) for row in rows]
            return ok({"success": True, "type": type, "database": target_db, "count": len(items), "items": items})
        except Exception as exc:  # noqa: BLE001
            raise tool_error(exc, "mysql_list", f"[list {type}]") from exc
